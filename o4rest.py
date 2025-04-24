#!/usr/bin/env python
from flask import Flask, request, jsonify, render_template_string
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# Filenames for storing data
SAVED_REQUESTS_FILE = 'saved_requests.json'
REQUEST_HISTORY_FILE = 'request_history.json'
MAX_HISTORY_SIZE = 20 # Limit history size

# --- Helper functions for file handling ---
def load_data(filename, default_data):
    """Loads data from a JSON file. Creates the file if it doesn't exist."""
    if not os.path.exists(filename):
        save_data(filename, default_data)
        return default_data
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # If the file is corrupt or unreadable, reset to default
        save_data(filename, default_data)
        return default_data

def save_data(filename, data):
    """Saves data to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving data to {filename}: {e}")

# Load initial data when the app starts
saved_requests_data = load_data(SAVED_REQUESTS_FILE, {})
request_history_data = load_data(REQUEST_HISTORY_FILE, [])

# --- HTML Template (Updated with English) ---
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>REST Client Tool</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; display: flex; gap: 20px; }
        .main-container { flex: 2; }
        .sidebar { flex: 1; border-left: 1px solid #ccc; padding-left: 20px; }
        .container { max-width: 800px; margin: auto; }
        input[type="text"], textarea, select { width: 100%; padding: 8px; margin: 5px 0 10px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        label { font-weight: bold; display: block; margin-bottom: 3px;}
        button { background-color: #4CAF50; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; margin-right: 5px; margin-top: 5px; }
        button:hover { background-color: #45a049; }
        button.delete { background-color: #f44336; }
        button.delete:hover { background-color: #da190b; }
        button.load { background-color: #008CBA; }
        button.load:hover { background-color: #007ba7; }
        .response { white-space: pre-wrap; background: #f4f4f4; padding: 10px; border-radius: 4px; border: 1px solid #ccc; margin-top: 15px; max-height: 400px; overflow-y: auto; }
        .section { margin-bottom: 20px; }
        .section h3 { margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 5px; }
        #savedRequestsList, #historyList { max-height: 200px; overflow-y: auto; border: 1px solid #eee; padding: 5px; margin-bottom: 10px; }
        .list-item { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; border-bottom: 1px dashed #eee; }
        .list-item:last-child { border-bottom: none; }
        .list-item span { flex-grow: 1; margin-right: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    </style>
</head>
<body>
    <div class="main-container">
        <h2>REST Client Tool</h2>
        <form id="restForm">
            <label for="url">URL:</label>
            <input type="text" id="url" name="url" placeholder="Enter URL" value="https://httpbin.org/get" required>

            <label for="method">HTTP Method:</label>
            <select id="method" name="method">
                <option>GET</option>
                <option>POST</option>
                <option>PUT</option>
                <option>DELETE</option>
                <option>PATCH</option>
                <option>OPTIONS</option>
            </select>

            <label for="headers">Headers (JSON format):</label>
            <textarea id="headers" name="headers" rows="4" placeholder='{"Content-Type": "application/json"}'></textarea>

            <label for="body">Request Body:</label>
            <textarea id="body" name="body" rows="6" placeholder="Enter request body"></textarea>

            <label>
                <input type="checkbox" id="proxy" name="proxy" style="width: auto; margin-right: 5px;">
                Use CORS Proxy
            </label>
            <br><br>
            <button type="submit">Send Request</button>
        </form>
        <h3>Response</h3>
        <div class="response" id="response">Waiting for request...</div>
    </div>

    <div class="sidebar">
        <div class="section">
            <h3>Saved Requests</h3>
            <label for="saveName">Save current as:</label>
            <input type="text" id="saveName" placeholder="Name for the request">
            <button onclick="saveCurrentRequest()">Save</button>
            <div id="savedRequestsList">Loading saved requests...</div>
        </div>

        <div class="section">
            <h3>History (Last {{ max_history }})</h3>
             <div id="historyList">Loading history...</div>
        </div>
    </div>

    <script>
        const urlEl = document.getElementById('url');
        const methodEl = document.getElementById('method');
        const headersEl = document.getElementById('headers');
        const bodyEl = document.getElementById('body');
        const proxyEl = document.getElementById('proxy');
        const responseEl = document.getElementById('response');
        const saveNameEl = document.getElementById('saveName');
        const savedRequestsListEl = document.getElementById('savedRequestsList');
        const historyListEl = document.getElementById('historyList');

        // --- Saved Requests Functions ---
        async function loadSavedRequests() {
            try {
                const response = await fetch('/saved');
                if (!response.ok) throw new Error('Could not fetch saved requests');
                const savedRequests = await response.json();
                savedRequestsListEl.innerHTML = ''; // Clear list
                if (Object.keys(savedRequests).length === 0) {
                    savedRequestsListEl.innerHTML = 'No saved requests.';
                    return;
                }
                // Sort names alphabetically
                const sortedNames = Object.keys(savedRequests).sort((a, b) => a.localeCompare(b));

                sortedNames.forEach(name => {
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    const span = document.createElement('span');
                    span.textContent = name;
                    span.title = name; // Show full name on hover
                    div.appendChild(span);

                    const loadButton = document.createElement('button');
                    loadButton.textContent = 'Load';
                    loadButton.className = 'load';
                    loadButton.onclick = () => loadRequestDetails(name, 'saved');
                    div.appendChild(loadButton);

                    const deleteButton = document.createElement('button');
                    deleteButton.textContent = 'Delete';
                    deleteButton.className = 'delete';
                    deleteButton.onclick = () => deleteSavedRequest(name);
                    div.appendChild(deleteButton);

                    savedRequestsListEl.appendChild(div);
                });
            } catch (error) {
                console.error("Error loading saved requests:", error);
                savedRequestsListEl.innerHTML = 'Error loading requests.';
            }
        }

        async function saveCurrentRequest() {
            const name = saveNameEl.value.trim();
            if (!name) {
                alert("Please enter a name to save the request.");
                return;
            }
            let requestData;
            try {
                 requestData = getCurrentRequestData(); // Includes header validation
            } catch (error) {
                // Error already alerted in getCurrentRequestData
                return;
            }

            try {
                const response = await fetch('/saved', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, ...requestData })
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Could not save the request');
                }
                saveNameEl.value = ''; // Clear the input field
                alert(`Request '${name}' saved.`);
                loadSavedRequests(); // Reload the list
            } catch (error) {
                console.error("Error saving request:", error);
                alert(`Error: ${error.message}`);
            }
        }

        async function deleteSavedRequest(name) {
            if (!confirm(`Are you sure you want to delete '${name}'?`)) {
                return;
            }
            try {
                const response = await fetch(`/saved/${encodeURIComponent(name)}`, { method: 'DELETE' });
                 if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Could not delete the request');
                }
                alert(`Request '${name}' deleted.`);
                loadSavedRequests(); // Reload the list
            } catch (error) {
                console.error("Error deleting request:", error);
                alert(`Error: ${error.message}`);
            }
        }

        // --- History Functions ---
        async function loadHistory() {
            try {
                const response = await fetch('/history');
                 if (!response.ok) throw new Error('Could not fetch history');
                const history = await response.json();
                historyListEl.innerHTML = ''; // Clear the list
                if (history.length === 0) {
                    historyListEl.innerHTML = 'No history yet.';
                    return;
                }
                history.forEach((item, index) => {
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    const span = document.createElement('span');
                    // Try to create a readable timestamp
                    let timeStr = '';
                    try {
                       // Use locale default, or specify 'en-US' / 'en-GB' etc. if needed
                       timeStr = new Date(item.timestamp).toLocaleString(undefined, {dateStyle: 'short', timeStyle: 'medium'});
                    } catch {
                       timeStr = item.timestamp; // Fallback
                    }
                    const displayText = `${item.method} ${item.url.substring(0, 30)}${item.url.length > 30 ? '...' : ''} (${timeStr})`;
                    span.textContent = displayText;
                    span.title = `${item.method} ${item.url}\n${timeStr}`; // Full info on hover
                    div.appendChild(span);

                    const loadButton = document.createElement('button');
                    loadButton.textContent = 'Load';
                    loadButton.className = 'load';
                    loadButton.onclick = () => loadRequestDetails(index, 'history');
                    div.appendChild(loadButton);
                    historyListEl.appendChild(div);
                });
            } catch (error) {
                console.error("Error loading history:", error);
                historyListEl.innerHTML = 'Error loading history.';
            }
        }


        // --- Common Functions ---
        function getCurrentRequestData() {
             // Validate headers before saving/sending
            let headers = {};
            let headersText = headersEl.value.trim();
            if (headersText) {
                try {
                    headers = JSON.parse(headersText); // Try parsing to validate
                } catch (e) {
                    alert("Invalid JSON format in Headers. Cannot save/send.");
                    throw new Error("Invalid JSON in headers");
                }
            }

            return {
                url: urlEl.value,
                method: methodEl.value,
                // Save headers as string to easily repopulate textarea
                headers: headersText,
                body: bodyEl.value,
                proxy: proxyEl.checked
            };
        }

        function populateForm(data) {
            urlEl.value = data.url || '';
            methodEl.value = data.method || 'GET';
            headersEl.value = data.headers || ''; // Restore as string
            bodyEl.value = data.body || '';
            proxyEl.checked = data.proxy || false;
        }

        async function loadRequestDetails(identifier, type) {
             try {
                let dataToLoad = null;
                if (type === 'saved') {
                    const response = await fetch(`/saved/${encodeURIComponent(identifier)}`);
                    if (!response.ok) throw new Error('Could not fetch saved request details');
                    dataToLoad = await response.json();
                } else if (type === 'history') {
                    // Fetch the whole history again and select the correct index
                    // (Alternative: an endpoint like /history/<index>)
                    const response = await fetch('/history');
                     if (!response.ok) throw new Error('Could not fetch history for loading');
                    const history = await response.json();
                    if (identifier >= 0 && identifier < history.length) {
                         dataToLoad = history[identifier];
                    } else {
                        throw new Error('Invalid history index');
                    }
                }

                if (dataToLoad) {
                    populateForm(dataToLoad);
                    responseEl.textContent = `Loaded '${type === 'saved' ? identifier : 'history item'}'. Send request to see results.`;
                    // Scroll form to top if needed
                    window.scrollTo(0, 0);
                }
            } catch (error) {
                console.error(`Error loading ${type}:`, error);
                alert(`Error: ${error.message}`);
            }
        }

        // --- Form Submit Event Listener ---
        document.getElementById('restForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            responseEl.textContent = 'Sending request...';
            let requestData;
            try {
                // Get current data, validates headers JSON
                requestData = getCurrentRequestData();
                 // Parse headers *again* to send as object to backend
                 let headersObj = {};
                 if(requestData.headers) {
                    // This parse should succeed because it was validated in getCurrentRequestData
                    headersObj = JSON.parse(requestData.headers);
                 }
                 const payload = { ...requestData, headers: headersObj }; // Send parsed object

                 const response = await fetch('/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                // Display regardless of ok status, as backend includes status_code/error
                responseEl.textContent = JSON.stringify(data, null, 2);
                loadHistory(); // Reload history after a request attempt

            } catch (error) {
                 // If the error was due to invalid JSON caught by getCurrentRequestData
                if (error.message === "Invalid JSON in headers") {
                     // The alert was already shown, just update response area
                     responseEl.textContent = "Error: Invalid JSON format in Headers.";
                     return; // Abort
                }
                // Other fetch or network errors
                console.error("Error sending request:", error);
                responseEl.textContent = `Error sending request: ${error}`;
                // Optionally load history even on failure for debugging
                // loadHistory();
            }
        });

        // --- Load initial data on page load ---
        document.addEventListener('DOMContentLoaded', () => {
            loadSavedRequests();
            loadHistory();
        });

    </script>
</body>
</html>
"""

# --- Flask Routes ---
@app.route("/")
def index():
    # Pass max history size to the template
    return render_template_string(HTML, max_history=MAX_HISTORY_SIZE)

@app.route("/request", methods=["POST"])
def make_request():
    global request_history_data # Allow modification of the global list

    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "Missing 'url' in request"}), 400

    url = data.get("url")
    method = data.get("method", "GET").upper()
    # Headers are now sent as an object from JS
    headers = data.get("headers", {})
    body = data.get("body", "")
    use_proxy = data.get("proxy", False)

    # --- Prepare details for history BEFORE the request ---
    # Advantage: Saved even if the request fails completely
    # Disadvantage: Timestamp is *before* the request completes
    # We save afterwards to get a more complete picture (including status)
    request_details_for_history = {
        "timestamp": datetime.utcnow().isoformat() + "Z", # ISO 8601 UTC
        "url": url,
        "method": method,
        # Store headers as string in history, like saved requests
        "headers": json.dumps(headers) if headers else "",
        "body": body,
        "proxy": use_proxy
    }

    result = {}
    status_code = 500 # Default for unexpected errors

    try:
        # Send body as JSON if Content-Type is application/json
        # Otherwise send as raw data (string)
        kwargs = {
            "headers": headers,
            "timeout": 10 # Add a timeout
        }
        if body:
            # Try to parse as JSON only if Content-Type header is set correctly
            if str(headers.get("Content-Type", "")).lower().strip() == "application/json":
                try:
                    # Use json= for requests library to handle serialization and Content-Type
                    kwargs["json"] = json.loads(body)
                except json.JSONDecodeError:
                    # If it's not valid JSON but header is set, send as data anyway? Or error?
                    # Sending as data here. Ensure it's bytes.
                     kwargs["data"] = body.encode('utf-8')
            else:
                 # Ensure body is bytes for the data argument
                 kwargs["data"] = body.encode('utf-8')

        resp = requests.request(method, url, **kwargs)

        status_code = resp.status_code
        result = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text # Always show text, even if it's JSON content
        }
    except requests.exceptions.Timeout:
        result = {"error": "Request timed out after 10 seconds."}
        status_code = 408
    except requests.exceptions.RequestException as e:
        result = { "error": f"Request failed: {str(e)}" }
        # Status code isn't set by the exception, default 500 might be misleading
        # Let's use a common code for connection errors if possible, or leave it
        status_code = 503 # Service Unavailable might fit network issues
    except Exception as e:
        result = { "error": f"An unexpected error occurred: {str(e)}" }
        status_code = 500


    # --- Save to history AFTER the request attempt ---
    # Optionally add status code to history item
    # request_details_for_history["status_code"] = status_code
    request_history_data.insert(0, request_details_for_history) # Add to beginning (newest)
    # Limit history size
    if len(request_history_data) > MAX_HISTORY_SIZE:
        request_history_data = request_history_data[:MAX_HISTORY_SIZE]
    # Save updated history to file
    save_data(REQUEST_HISTORY_FILE, request_history_data)

    # --- Send response to client ---
    response = jsonify(result)
    response.status_code = status_code # Set the HTTP status for the Flask response itself
    if use_proxy:
        # This is a very simple CORS proxy, might need more headers in production
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")

    return response

# --- Endpoints for Saved Requests ---
@app.route("/saved", methods=["GET"])
def get_saved_requests():
    """Returns all saved requests (names and data)."""
    # Read from file each time to get latest data (alternative: use global)
    data = load_data(SAVED_REQUESTS_FILE, {})
    return jsonify(data)

@app.route("/saved/<name>", methods=["GET"])
def get_saved_request_details(name):
    """Returns details for a specific saved request."""
    data = load_data(SAVED_REQUESTS_FILE, {})
    if name in data:
        return jsonify(data[name])
    else:
        return jsonify({"error": "Saved request not found"}), 404

@app.route("/saved", methods=["POST"])
def add_saved_request():
    """Saves a new request."""
    global saved_requests_data # Use global variable to update in memory
    req_data = request.get_json()
    name = req_data.get('name')
    if not name:
        return jsonify({"error": "Missing 'name' for saved request"}), 400

    # Read current data from file first to avoid overwrites in concurrent scenarios (unlikely here)
    current_data = load_data(SAVED_REQUESTS_FILE, {})

    current_data[name] = {
        "url": req_data.get("url", ""),
        "method": req_data.get("method", "GET"),
        "headers": req_data.get("headers", ""), # Save as string
        "body": req_data.get("body", ""),
        "proxy": req_data.get("proxy", False)
    }
    saved_requests_data = current_data # Update global variable too
    save_data(SAVED_REQUESTS_FILE, current_data)
    return jsonify({"message": f"Request '{name}' saved successfully."}), 201

@app.route("/saved/<name>", methods=["DELETE"])
def delete_saved_request(name):
    """Deletes a saved request."""
    global saved_requests_data
    current_data = load_data(SAVED_REQUESTS_FILE, {})
    if name in current_data:
        del current_data[name]
        saved_requests_data = current_data # Update global
        save_data(SAVED_REQUESTS_FILE, current_data)
        return jsonify({"message": f"Request '{name}' deleted successfully."}), 200
    else:
        return jsonify({"error": "Saved request not found"}), 404

# --- Endpoint for History ---
@app.route("/history", methods=["GET"])
def get_history():
    """Returns the request history."""
    # Read from file each time for latest data
    data = load_data(REQUEST_HISTORY_FILE, [])
    return jsonify(data)


if __name__ == "__main__":
    print(f"Saved requests will be stored in: {os.path.abspath(SAVED_REQUESTS_FILE)}")
    print(f"History will be stored in: {os.path.abspath(REQUEST_HISTORY_FILE)}")
    # Set host='0.0.0.0' to make it accessible on your network (use with caution)
    app.run(debug=True) # debug=True enables auto-reloading and error pages