#!/usr/bin/env python3
from flask import (
    Flask,
    request,
    redirect,
    url_for,
    render_template,
    # jsonify,
    send_from_directory,
)
import pandas as pd
import mysql.connector
import os
import threading

# import json
from flask_socketio import SocketIO
from dotenv import load_dotenv

app = Flask(__name__)
socketio = SocketIO(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect(url_for("index"))

    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("index"))

    if file:
        df = pd.read_excel(file)
        column_to_use = request.form["column"]

        if column_to_use not in df.columns:
            socketio.emit(
                "update_progress",
                {
                    "progress": -1,
                    "error_message": f'Column "{column_to_use}" not found in the uploaded file.',
                },
            )
            return redirect(url_for("progress"))

        connection = create_db_connection()
        threading.Thread(
            target=process_file, args=(df, column_to_use, connection)
        ).start()

        return redirect(url_for("progress"))


@app.route("/progress")
def progress():
    return render_template("progress.html")


@app.route("/download/<filename>")
def download_file(filename):
    download_folder = os.path.expanduser("~/Downloads")
    return send_from_directory(download_folder, filename, as_attachment=True)


def create_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_SCHEMA"),
    )


def fetch_status_wo_url(last_36, connection):
    cursor = connection.cursor()
    query = "SELECT status FROM work_orders WHERE guid = %s"
    cursor.execute(query, (last_36,))
    result = cursor.fetchone()
    cursor.close()
    return result[0] if result else "Not Found"


def fetch_service_status(last_36, connection):
    cursor = connection.cursor()
    query = """
    SELECT
        CASE status_id
            WHEN 1 THEN 'Expression of Interest'
            WHEN 2 THEN 'Active'
            WHEN 3 THEN 'Pending ISP Application'
            WHEN 4 THEN 'Pending Installation'
            WHEN 5 THEN 'Pending ISP Activation'
            WHEN 6 THEN 'Activation in Progress'
            WHEN 7 THEN 'Expiring'
            WHEN 8 THEN 'Expired'
            WHEN 9 THEN 'Cancellation in Progress'
            WHEN 10 THEN 'Cancelled'
            WHEN 11 THEN 'ISP Changed'
            WHEN 12 THEN 'ISP Change Pending'
            WHEN 13 THEN 'Product Changed'
            WHEN 14 THEN 'Product Change Pending'
            WHEN 15 THEN 'Rejected'
            WHEN 16 THEN 'Suspended'
            ELSE 'Unknown'
        END AS status_name
    FROM services
    WHERE aex_id = %s
    """
    cursor.execute(query, (last_36,))
    result = cursor.fetchone()
    cursor.close()
    return result[0] if result else "Not Found"


def process_file(df, column_to_use, connection):
    total_rows = len(df)
    chunk_size = max(total_rows // 100, 1)
    completed_rows = 0

    status_counts = {}
    status_list = []

    try:
        if column_to_use == "WO URL":
            df["Last_36_Chars"] = df["WO URL"].apply(lambda url: url[-36:])
        elif column_to_use == "Service URL":
            df["Last_36_Chars"] = df["Service URL"].apply(
                lambda service_id: service_id[-36:]
            )

        for start in range(0, total_rows, chunk_size):
            end = start + chunk_size
            chunk = df.iloc[start:end].copy()

            if column_to_use == "WO URL":
                chunk["Status"] = chunk["Last_36_Chars"].apply(
                    lambda last_36: fetch_status_wo_url(last_36, connection)
                )
            elif column_to_use == "Service URL":
                chunk["Status"] = chunk["Last_36_Chars"].apply(
                    lambda last_36: fetch_service_status(last_36, connection)
                )

            for status in chunk["Status"]:
                if status in status_counts:
                    status_counts[status] += 1
                else:
                    status_counts[status] = 1

            status_list.append(chunk)
            completed_rows += chunk_size

            progress = (completed_rows / total_rows) * 100
            socketio.emit("update_progress", {"progress": progress})

        result_df = pd.concat(status_list, ignore_index=True)
        output_filename = f'{column_to_use.lower().replace(" ", "_")}_status.xlsx'
        download_folder = os.path.expanduser("~/Downloads")
        output_excel_path = os.path.join(download_folder, output_filename)
        result_df.to_excel(output_excel_path, index=False)

        socketio.emit(
            "update_progress",
            {
                "progress": 100,
                "status_message": f"Status saved to {output_excel_path}",
                "filename": output_filename,
            },
        )

    except Exception as e:
        print(f"Error processing file: {e}")
        socketio.emit("update_progress", {"progress": -1, "error_message": str(e)})

    finally:
        connection.close()


if __name__ == "__main__":
    load_dotenv()

    app_port = os.getenv("APP_PORT")
    debug_mode = os.getenv("DEBUG")

    socketio.run(app, host="0.0.0.0", port=app_port, debug=debug_mode)
