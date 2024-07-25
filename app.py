#!/usr/bin/env python3
from flask import (
    Flask,
    request,
    redirect,
    url_for,
    render_template,
    send_from_directory,
)
import pandas as pd
import mysql.connector
import os
import threading
import re
import datetime
import random
import string

from flask_socketio import SocketIO
from dotenv import load_dotenv


app = Flask(__name__)
socketio = SocketIO(app)
files_dir=""

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

        connection = create_db_connection()
        threading.Thread(
            target=process_file, args=(df, connection)
        ).start()

        return redirect(url_for("progress"))


@app.route("/progress")
def progress():
    return render_template("progress.html")


@app.route("/download/<filename>")
def download_file(filename):
    download_folder = os.path.expanduser(files_dir)
    return send_from_directory(download_folder, filename, as_attachment=True)


def create_db_connection():
    load_dotenv()
    return mysql.connector.connect(
        host=str(os.getenv("DB_HOST")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_SCHEMA"),
    )

def convert_status_id_to_service_status(status_id):
    print (status_id)
    status_map = {
        1: 'Expression of Interest',
        2: 'Active',
        3: 'Pending ISP Application',
        4: 'Pending Installation',
        5: 'Pending ISP Activation',
        6: 'Activation in Progress',
        7: 'Expiring',
        8: 'Expired',
        9: 'Cancellation in Progress',
        10: 'Cancelled',
        11: 'ISP Changed',
        12: 'ISP Change Pending',
        13: 'Product Changed',
        14: 'Product Change Pending',
        15: 'Rejected',
        16: 'Suspended'
    }

    return status_map.get(status_id, 'Unknown')

def get_scalar_result(query, connection):
    cursor = connection.cursor()
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return result[0] if result else "Not Found"

def get_work_order_status(uuid, connection):
    query = f"SELECT status FROM work_orders WHERE guid = '{uuid}' LIMIT 1"
    return get_scalar_result(query, connection)

def get_service_status(uuid, connection):
    query = f"SELECT status_id FROM services WHERE aex_id = '{uuid}' LIMIT 1"
    return get_scalar_result(query, connection)

def extract_uuid_from_string(input_string):
    # return "3D97D2AD-C18D-471B-9A29-E0003FFA64D2"
    uuid_pattern = re.compile(r'\b[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}\b', re.IGNORECASE)
    matches = uuid_pattern.findall(input_string)

    if matches:
        return matches[-1]
    else:
        return None

def process_file(df, connection):
    total_rows = len(df)
    progress_report_frequency = 15

    try:
        for row_number, row in df.iterrows():
            uuid = extract_uuid_from_string(row["Service URL"])
            df.at[row_number, "Service Status"] = convert_status_id_to_service_status(get_service_status(uuid, connection))
            uuid = extract_uuid_from_string(row["WO URL"])
            df.at[row_number, "Work Order Status"] = get_work_order_status(uuid, connection)
            df.at[row_number, "Commission Due"] = "Yes" if df.at[row_number,"Service Status"] == "Active" and df.at[row_number,"Work Order Status"] == "Installation Complete" else "No"
            if row_number % progress_report_frequency == 0:
                percentage_complete = (row_number / total_rows) * 100
                socketio.emit("update_progress", {"progress": percentage_complete})

        output_file = generate_filename()
        df.to_excel(output_file, index=False)

        socketio.emit(
            "update_progress",
            {
                "progress": 100,
                "filename": output_file,
            },
        )

    except Exception as e:
        print(f"Error processing file: {e}")
        socketio.emit("update_progress", {"progress": -1, "error_message": str(e)})

    finally:
        connection.close()

def generate_filename():
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_id = ''.join(random.choices(string.digits, k=8))
    filename = f"{today_date}_{unique_id}.xlsx"
    return filename

if __name__ == "__main__":
    load_dotenv()
    app_port = os.getenv("APP_PORT")
    debug_mode = os.getenv("DEBUG") == "True"
    socketio.run(app, host="0.0.0.0", port=app_port, debug=debug_mode)
