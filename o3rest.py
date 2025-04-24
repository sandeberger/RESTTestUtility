#!/usr/bin/env python
from flask import Flask, request, jsonify, render_template_string
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# Filnamn för att spara data
SAVED_REQUESTS_FILE = 'saved_requests.json'
REQUEST_HISTORY_FILE = 'request_history.json'
MAX_HISTORY_SIZE = 20 # Begränsa historikens storlek

# --- Hjälpfunktioner för filhantering ---
def load_data(filename, default_data):
    """Laddar data från en JSON-fil. Skapar filen om den inte finns."""
    if not os.path.exists(filename):
        save_data(filename, default_data)
        return default_data
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Om filen är korrupt eller oläsbar, återställ till default
        save_data(filename, default_data)
        return default_data

def save_data(filename, data):
    """Sparar data till en JSON-fil."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving data to {filename}: {e}")

# Ladda initial data när appen startar
saved_requests_data = load_data(SAVED_REQUESTS_FILE, {})
request_history_data = load_data(REQUEST_HISTORY_FILE, [])

# --- HTML-mall (Uppdaterad) ---
HTML = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <title>REST Testverktyg</title>
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
        <h2>REST Testverktyg</h2>
        <form id="restForm">
            <label for="url">URL:</label>
            <input type="text" id="url" name="url" placeholder="Ange URL" value="https://httpbin.org/get" required>

            <label for="method">HTTP-metod:</label>
            <select id="method" name="method">
                <option>GET</option>
                <option>POST</option>
                <option>PUT</option>
                <option>DELETE</option>
                <option>PATCH</option>
                <option>OPTIONS</option>
            </select>

            <label for="headers">Headers (JSON-format):</label>
            <textarea id="headers" name="headers" rows="4" placeholder='{"Content-Type": "application/json"}'></textarea>

            <label for="body">Request Body:</label>
            <textarea id="body" name="body" rows="6" placeholder="Ange request body"></textarea>

            <label>
                <input type="checkbox" id="proxy" name="proxy" style="width: auto; margin-right: 5px;">
                Använd CORS-Proxy
            </label>
            <br><br>
            <button type="submit">Skicka anrop</button>
        </form>
        <h3>Response</h3>
        <div class="response" id="response">Väntar på anrop...</div>
    </div>

    <div class="sidebar">
        <div class="section">
            <h3>Sparade Anrop</h3>
            <label for="saveName">Spara nuvarande som:</label>
            <input type="text" id="saveName" placeholder="Namn på anropet">
            <button onclick="saveCurrentRequest()">Spara</button>
            <div id="savedRequestsList">Laddar sparade anrop...</div>
        </div>

        <div class="section">
            <h3>Historik (Senaste {{ max_history }})</h3>
             <div id="historyList">Laddar historik...</div>
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

        // --- Funktioner för sparade anrop ---
        async function loadSavedRequests() {
            try {
                const response = await fetch('/saved');
                if (!response.ok) throw new Error('Kunde inte hämta sparade anrop');
                const savedRequests = await response.json();
                savedRequestsListEl.innerHTML = ''; // Rensa listan
                if (Object.keys(savedRequests).length === 0) {
                    savedRequestsListEl.innerHTML = 'Inga sparade anrop.';
                    return;
                }
                // Sortera namnen alfabetiskt
                const sortedNames = Object.keys(savedRequests).sort((a, b) => a.localeCompare(b));

                sortedNames.forEach(name => {
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    const span = document.createElement('span');
                    span.textContent = name;
                    span.title = name; // Visa hela namnet på hover
                    div.appendChild(span);

                    const loadButton = document.createElement('button');
                    loadButton.textContent = 'Ladda';
                    loadButton.className = 'load';
                    loadButton.onclick = () => loadRequestDetails(name, 'saved');
                    div.appendChild(loadButton);

                    const deleteButton = document.createElement('button');
                    deleteButton.textContent = 'Ta bort';
                    deleteButton.className = 'delete';
                    deleteButton.onclick = () => deleteSavedRequest(name);
                    div.appendChild(deleteButton);

                    savedRequestsListEl.appendChild(div);
                });
            } catch (error) {
                console.error("Fel vid laddning av sparade anrop:", error);
                savedRequestsListEl.innerHTML = 'Fel vid laddning.';
            }
        }

        async function saveCurrentRequest() {
            const name = saveNameEl.value.trim();
            if (!name) {
                alert("Ange ett namn för att spara anropet.");
                return;
            }
            const requestData = getCurrentRequestData();
            try {
                const response = await fetch('/saved', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, ...requestData })
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Kunde inte spara anropet');
                }
                saveNameEl.value = ''; // Rensa fältet
                alert(`Anropet '${name}' sparades.`);
                loadSavedRequests(); // Ladda om listan
            } catch (error) {
                console.error("Fel vid sparning:", error);
                alert(`Fel: ${error.message}`);
            }
        }

        async function deleteSavedRequest(name) {
            if (!confirm(`Är du säker på att du vill ta bort '${name}'?`)) {
                return;
            }
            try {
                const response = await fetch(`/saved/${encodeURIComponent(name)}`, { method: 'DELETE' });
                 if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Kunde inte ta bort anropet');
                }
                alert(`Anropet '${name}' togs bort.`);
                loadSavedRequests(); // Ladda om listan
            } catch (error) {
                console.error("Fel vid borttagning:", error);
                alert(`Fel: ${error.message}`);
            }
        }

        // --- Funktioner för historik ---
        async function loadHistory() {
            try {
                const response = await fetch('/history');
                 if (!response.ok) throw new Error('Kunde inte hämta historik');
                const history = await response.json();
                historyListEl.innerHTML = ''; // Rensa listan
                if (history.length === 0) {
                    historyListEl.innerHTML = 'Ingen historik än.';
                    return;
                }
                history.forEach((item, index) => {
                    const div = document.createElement('div');
                    div.className = 'list-item';
                    const span = document.createElement('span');
                    // Försök skapa en läsbar tid
                    let timeStr = '';
                    try {
                       timeStr = new Date(item.timestamp).toLocaleString('sv-SE');
                    } catch {
                       timeStr = item.timestamp; // Fallback
                    }
                    const displayText = `${item.method} ${item.url.substring(0, 30)}${item.url.length > 30 ? '...' : ''} (${timeStr})`;
                    span.textContent = displayText;
                    span.title = `${item.method} ${item.url}\n${timeStr}`; // Full info på hover
                    div.appendChild(span);

                    const loadButton = document.createElement('button');
                    loadButton.textContent = 'Ladda';
                    loadButton.className = 'load';
                    // Vi behöver skicka index för att backend ska kunna hämta rätt item
                    // Eller bättre, skicka hela objektet när vi laddar
                    loadButton.onclick = () => loadRequestDetails(index, 'history');
                    div.appendChild(loadButton);
                    historyListEl.appendChild(div);
                });
            } catch (error) {
                console.error("Fel vid laddning av historik:", error);
                historyListEl.innerHTML = 'Fel vid laddning.';
            }
        }


        // --- Gemensamma funktioner ---
        function getCurrentRequestData() {
             // Validera headers innan vi sparar/skickar
            let headers = {};
            let headersText = headersEl.value.trim();
            if (headersText) {
                try {
                    headers = JSON.parse(headersText);
                } catch (e) {
                    // Hantera ogiltig JSON i headers - kan returnera null eller kasta fel
                    alert("Ogiltigt JSON-format i Headers. Kan inte spara/skicka.");
                    throw new Error("Invalid JSON in headers");
                }
            }

            return {
                url: urlEl.value,
                method: methodEl.value,
                // Spara headers som sträng för att enkelt kunna återställa i textarean
                headers: headersText,
                body: bodyEl.value,
                proxy: proxyEl.checked
            };
        }

        function populateForm(data) {
            urlEl.value = data.url || '';
            methodEl.value = data.method || 'GET';
            headersEl.value = data.headers || ''; // Återställ som sträng
            bodyEl.value = data.body || '';
            proxyEl.checked = data.proxy || false;
        }

        async function loadRequestDetails(identifier, type) {
             try {
                let dataToLoad = null;
                if (type === 'saved') {
                    const response = await fetch(`/saved/${encodeURIComponent(identifier)}`);
                    if (!response.ok) throw new Error('Kunde inte hämta sparat anrop');
                    dataToLoad = await response.json();
                } else if (type === 'history') {
                    // Hämta hela historiken igen och välj rätt index
                    // (Alternativt: en endpoint /history/<index>)
                    const response = await fetch('/history');
                     if (!response.ok) throw new Error('Kunde inte hämta historik för laddning');
                    const history = await response.json();
                    if (identifier >= 0 && identifier < history.length) {
                         dataToLoad = history[identifier];
                    } else {
                        throw new Error('Ogiltigt historikindex');
                    }
                }

                if (dataToLoad) {
                    populateForm(dataToLoad);
                    responseEl.textContent = `Laddade '${type === 'saved' ? identifier : 'historik-item'}'. Skicka anrop för att se resultat.`;
                    // Scrolla formuläret till toppen om det behövs
                    window.scrollTo(0, 0);
                }
            } catch (error) {
                console.error(`Fel vid laddning av ${type}:`, error);
                alert(`Fel: ${error.message}`);
            }
        }

        // --- Event Listener för formuläret ---
        document.getElementById('restForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            responseEl.textContent = 'Skickar anrop...';
            let requestData;
            try {
                // Hämta aktuell data, validera headers JSON
                requestData = getCurrentRequestData();
                 // Parse headers *igen* för att skicka som objekt till backend
                 let headersObj = {};
                 if(requestData.headers) {
                    headersObj = JSON.parse(requestData.headers);
                 }
                 const payload = { ...requestData, headers: headersObj }; // Skicka parsat objekt

                 const response = await fetch('/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                responseEl.textContent = JSON.stringify(data, null, 2);
                loadHistory(); // Ladda om historiken efter ett lyckat anrop

            } catch (error) {
                 // Om felet var pga ogiltig JSON i getCurrentRequestData
                if (error.message === "Invalid JSON in headers") {
                     responseEl.textContent = "Fel: Ogiltigt JSON-format i Headers.";
                     return; // Avbryt
                }
                // Annat fel
                console.error("Fel vid anrop:", error);
                responseEl.textContent = `Fel vid anrop: ${error}`;
                // Ladda historiken även vid fel? Kanske bra för felsökning.
                // loadHistory();
            }
        });

        // --- Ladda initial data vid sidladdning ---
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
    # Skicka med max historikstorlek till mallen
    return render_template_string(HTML, max_history=MAX_HISTORY_SIZE)

@app.route("/request", methods=["POST"])
def make_request():
    global request_history_data # Tillåt modifiering av globala listan

    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "Missing 'url' in request"}), 400

    url = data.get("url")
    method = data.get("method", "GET").upper()
    # Headers skickas nu som objekt från JS
    headers = data.get("headers", {})
    body = data.get("body", "")
    use_proxy = data.get("proxy", False)

    # --- Spara till historik FÖRE anropet (eller efter?) ---
    # Fördel med före: Sparas även om anropet misslyckas helt
    # Nackdel: Timestamp är *innan* anropet är klart
    # Vi sparar efteråt för att få en mer komplett bild om anropet lyckas/misslyckas
    request_details_for_history = {
        "timestamp": datetime.utcnow().isoformat() + "Z", # ISO 8601 UTC
        "url": url,
        "method": method,
        # Spara headers som sträng i historiken, som i sparade anrop
        "headers": json.dumps(headers) if headers else "",
        "body": body,
        "proxy": use_proxy
    }

    result = {}
    status_code = 500 # Default vid oväntat fel

    try:
        # Skicka body som JSON om Content-Type är application/json
        # Annars skicka som rådata (sträng)
        kwargs = {
            "headers": headers,
            "timeout": 10 # Lägg till en timeout
        }
        if body:
            # Försök tolka som JSON endast om Content-Type är satt
            if str(headers.get("Content-Type", "")).lower().strip() == "application/json":
                try:
                    kwargs["json"] = json.loads(body) # Använd json= för requests
                except json.JSONDecodeError:
                    # Om det inte är giltig JSON men headern är satt, skicka som data ändå?
                    # Eller returnera fel? Vi skickar som data här.
                     kwargs["data"] = body.encode('utf-8') # Se till att det är bytes
            else:
                 kwargs["data"] = body.encode('utf-8') # Se till att det är bytes

        resp = requests.request(method, url, **kwargs)

        status_code = resp.status_code
        result = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text # Visa alltid text, även om det är JSON
        }
    except requests.exceptions.Timeout:
        result = {"error": "Request timed out after 10 seconds."}
        status_code = 408
    except requests.exceptions.RequestException as e:
        result = { "error": f"Request failed: {str(e)}" }
        # Statuskoden sätts inte här, men vi kan gissa 500 eller liknande
    except Exception as e:
        result = { "error": f"An unexpected error occurred: {str(e)}" }
        status_code = 500


    # --- Spara till historik EFTER anropet ---
    # Lägg till statuskod i historiken? Kan vara användbart.
    # request_details_for_history["status_code"] = status_code # Valfritt
    request_history_data.insert(0, request_details_for_history) # Lägg till först (nyast)
    # Begränsa historikens storlek
    if len(request_history_data) > MAX_HISTORY_SIZE:
        request_history_data = request_history_data[:MAX_HISTORY_SIZE]
    # Spara uppdaterad historik till fil
    save_data(REQUEST_HISTORY_FILE, request_history_data)

    # --- Skicka svar till klienten ---
    response = jsonify(result)
    response.status_code = status_code # Sätt HTTP-status för Flask-svaret
    if use_proxy:
        # Detta är en enkel CORS-proxy, kan behöva mer finess i produktion
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")

    return response

# --- Endpoints för sparade anrop ---
@app.route("/saved", methods=["GET"])
def get_saved_requests():
    """Returnerar alla sparade anrop (bara namnen och datan)."""
    # Läs från fil varje gång för att få senaste data (alternativt använd global)
    data = load_data(SAVED_REQUESTS_FILE, {})
    return jsonify(data)

@app.route("/saved/<name>", methods=["GET"])
def get_saved_request_details(name):
    """Returnerar detaljer för ett specifikt sparat anrop."""
    data = load_data(SAVED_REQUESTS_FILE, {})
    if name in data:
        return jsonify(data[name])
    else:
        return jsonify({"error": "Saved request not found"}), 404

@app.route("/saved", methods=["POST"])
def add_saved_request():
    """Sparar ett nytt anrop."""
    global saved_requests_data # Använd globala variabeln för att uppdatera
    req_data = request.get_json()
    name = req_data.get('name')
    if not name:
        return jsonify({"error": "Missing 'name' for saved request"}), 400

    # Läs aktuell data från fil först för att undvika överskrivning vid samtidighet (även om osannolikt här)
    current_data = load_data(SAVED_REQUESTS_FILE, {})

    current_data[name] = {
        "url": req_data.get("url", ""),
        "method": req_data.get("method", "GET"),
        "headers": req_data.get("headers", ""), # Spara som sträng
        "body": req_data.get("body", ""),
        "proxy": req_data.get("proxy", False)
    }
    saved_requests_data = current_data # Uppdatera globala variabeln också
    save_data(SAVED_REQUESTS_FILE, current_data)
    return jsonify({"message": f"Request '{name}' saved successfully."}), 201

@app.route("/saved/<name>", methods=["DELETE"])
def delete_saved_request(name):
    """Tar bort ett sparat anrop."""
    global saved_requests_data
    current_data = load_data(SAVED_REQUESTS_FILE, {})
    if name in current_data:
        del current_data[name]
        saved_requests_data = current_data # Uppdatera globala
        save_data(SAVED_REQUESTS_FILE, current_data)
        return jsonify({"message": f"Request '{name}' deleted successfully."}), 200
    else:
        return jsonify({"error": "Saved request not found"}), 404

# --- Endpoint för historik ---
@app.route("/history", methods=["GET"])
def get_history():
    """Returnerar request-historiken."""
    # Läs från fil varje gång för att få senaste data
    data = load_data(REQUEST_HISTORY_FILE, [])
    return jsonify(data)


if __name__ == "__main__":
    print(f"Sparade anrop lagras i: {os.path.abspath(SAVED_REQUESTS_FILE)}")
    print(f"Historik lagras i: {os.path.abspath(REQUEST_HISTORY_FILE)}")
    app.run(debug=True)