
function uploadFile() {
    const form = document.getElementById('upload-form');
    const formData = new FormData(form);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.text();
    })
    .then(data => {
        const statusResults = document.getElementById('status-results');
        statusResults.innerHTML = data; // Display HTML table with results
    })
    .catch(error => {
        console.error('Error:', error);
        const errorMessage = document.getElementById('error-message');
        errorMessage.textContent = 'Failed to fetch data. Please check server logs for details.';
        errorMessage.style.display = 'block';
    });
}
