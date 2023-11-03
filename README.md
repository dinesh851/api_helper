<!DOCTYPE html>
<html>
<head>
  <title>API Helper and WebSocket Connection README</title>
</head>
<body>

<h1>API Helper and WebSocket Connection README</h1>

<h2>Introduction</h2>

<p>This repository contains a Python-based API helper and WebSocket connection implementation. The purpose of this project is to facilitate the communication between a broker and a server, allowing the seamless transfer of data in real-time.</p>

<h2>Setup</h2>

<ol>
  <li>Clone the repository: <code>git clone https://github.com/your_username/api-websocket-helper.git</code></li>
  <li>Navigate to the project directory: <code>cd api-websocket-helper</code></li>
  <li>Install the required dependencies: <code>pip install -r requirements.txt</code></li>
</ol>

<h2>API Helper</h2>

<ol>
  <li>Import the <code>api_helper</code> module: <code>from api_helper import APIHelper</code></li>
  <li>Instantiate the <code>APIHelper</code> class with your API credentials: <code>api = APIHelper(api_key='your_api_key', secret_key='your_secret_key')</code></li>
  <li>Utilize the available methods within the <code>APIHelper</code> class to interact with the broker's API.</li>
</ol>

<h2>WebSocket Connection</h2>

<ol>
  <li>Import the <code>websocket_connection</code> module: <code>from websocket_connection import WebSocketConnection</code></li>
  <li>Instantiate the <code>WebSocketConnection</code> class with the required parameters: <code>ws = WebSocketConnection(url='wss://your_websocket_url', on_message_callback=handle_message)</code></li>
  <li>Define the <code>handle_message</code> function to process incoming WebSocket messages.</li>
  <li>Start the WebSocket connection: <code>ws.start()</code></li>
</ol>

<h2>Server to Get Data from Broker</h2>

<ol>
  <li>Import the required modules: <code>from http.server import BaseHTTPRequestHandler, HTTPServer</code></li>
  <li>Define the <code>DataHandler</code> class to handle HTTP requests and retrieve data from the broker using the <code>APIHelper</code> class.</li>
  <li>Implement the server logic within the <code>DataHandler</code> class.</li>
  <li>Start the server: <code>server_address = ('', 8000) <!-- Replace 8000 with your desired port --></code></li>
</ol>

<h2>License</h2>

<p>This project is licensed under the MIT License. See the LICENSE file for more information.</p>

</body>
</html>
