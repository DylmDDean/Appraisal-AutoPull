<?php
// public/index.php
// PHP front-end: server-side POST to Flask backend using cURL and show JSON response.
// County is required; Grant county requires a city selection.

$apiUrl = getenv('FLASK_API_URL') ?: "http://localhost:5000/api/send-requests";

$response = null;
$error = null;
$success_message = null;
$isPost = $_SERVER['REQUEST_METHOD'] === 'POST';

// Helper: safely get posted value
function postval($key, $default = '') {
    return isset($_POST[$key]) ? $_POST[$key] : $default;
}

$selectedCounty = strtolower(trim(postval('county', '')));

if ($isPost) {
    $address = trim(postval('address', ''));
    $city = trim(postval('city', ''));
    $county = trim(postval('county', ''));
    $property_id = trim(postval('property_id', ''));
    $send_to_pva = isset($_POST['send_to_pva']) ? true : false;
    $send_to_zoning = isset($_POST['send_to_zoning']) ? true : false;

    // Validate required fields
    if ($address === '') {
        $error = "Address is required.";
    } elseif ($county === '') {
        $error = "County is required.";
    } elseif (strtolower(trim($county)) === 'grant' && $city === '') {
        $error = "City is required if county is Grant.";
    } else {
        $payload = [
            'address' => $address,
            'county' => $county,
            'send_to_pva' => $send_to_pva,
            'send_to_zoning' => $send_to_zoning
        ];
        if ($city !== '') $payload['city'] = $city;
        if ($property_id !== '') $payload['property_id'] = $property_id;

        $ch = curl_init($apiUrl);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);
        curl_setopt($ch, CURLOPT_TIMEOUT, 15);

        $raw = curl_exec($ch);
        if ($raw === false) {
            $error = curl_error($ch);
        } else {
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $decoded = json_decode($raw, true);
            $response = [
                'http_code' => $httpCode,
                'body' => $decoded ?? $raw
            ];
            if ($httpCode >= 200 && $httpCode < 300) {
                $success_message = "Request sent successfully.";
            } else {
                // if non-2xx, show returned error body if available
                if (is_array($response['body']) && isset($response['body']['error'])) {
                    $error = $response['body']['error'];
                }
            }
        }
        curl_close($ch);
    }
}

// checkbox defaults: checked by default on initial load; respect submitted values after POST
$checked_pva = $isPost ? (isset($_POST['send_to_pva']) ? 'checked' : '') : 'checked';
$checked_zoning = $isPost ? (isset($_POST['send_to_zoning']) ? 'checked' : '') : 'checked';

?>
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Send Requests — PHP Frontend</title>
  <link rel="stylesheet" href="style.css">
  <meta name="viewport" content="width=device-width,initial-scale=1" />
</head>
<body>
  <div class="container" style="max-width:760px;margin:24px auto;padding:16px;">
    <h1>Send Requests</h1>

    <form method="post" novalidate>
      <label>Address (required)
        <input type="text" name="address" required value="<?= htmlspecialchars(postval('address', ''), ENT_QUOTES) ?>" style="width:100%;padding:8px;margin-top:6px"/>
      </label>

      <label id="city-label" style="display:block;margin-top:12px">
        <span id="city-label-text">City (optional)</span>
        <span id="city-input-container" style="display:block;margin-top:6px">
          <input type="text" name="city" value="<?= htmlspecialchars(postval('city', ''), ENT_QUOTES) ?>" style="width:100%;padding:8px" />
        </span>
      </label>

      <label style="display:block;margin-top:12px">County (required)
        <?php
          // list of counties used by the app; keep values in lowercase
          $counties = ['anderson','boone','carroll','franklin','gallatin','grant','kenton','owen','scott','trimble'];
        ?>
        <select name="county" required style="width:100%;padding:8px;margin-top:6px">
          <option value="" disabled <?= $selectedCounty === '' ? 'selected' : '' ?>>Select a county</option>
          <?php foreach ($counties as $c): ?>
            <option value="<?= htmlspecialchars($c, ENT_QUOTES) ?>" <?= ($selectedCounty === $c) ? 'selected' : '' ?>><?= htmlspecialchars($c) ?></option>
          <?php endforeach; ?>
        </select>
      </label>

      <!-- Send checkboxes -->
      <label style="display:block;margin-top:12px">
        <input type="checkbox" name="send_to_pva" <?= $checked_pva ?> />
        Send to PVA
      </label>
      <label style="display:block;margin-top:6px">
        <input type="checkbox" name="send_to_zoning" <?= $checked_zoning ?> />
        Send to Zoning
      </label>

      <div class="actions" style="margin-top:16px">
        <button type="submit" style="padding:10px 16px;font-size:1rem">Send</button>
        <a class="btn-ghost" href="index.html" style="margin-left:12px;color:#666;text-decoration:none">Try AJAX front-end</a>
      </div>
    </form>

    <!-- Inserted email-capture UI block (saves user contact & triggers /save_email) -->
    <div id="save-email-block" style="max-width:420px;margin:20px auto;padding:16px;border:1px solid #eee;border-radius:8px;">
      <h3>Save your contact</h3>
      <p style="font-size:0.9em;color:#555">Enter your email so replies from officials go to you. We’ll send one quick confirmation.</p>
      <input id="email-input" name="email" type="email" placeholder="you@example.com" style="width:100%;padding:10px;margin:8px 0;border-radius:6px;border:1px solid #ccc" />
      <input id="name-input" name="name" type="text" placeholder="Your name (optional)" style="width:100%;padding:10px;margin:8px 0;border-radius:6px;border:1px solid #ccc" />
      <label style="display:block;margin-bottom:8px;font-size:0.9em;">
        <input id="optin-checkbox" type="checkbox" checked /> I agree to have my contact used to send requests
      </label>
      <button id="save-email-btn" style="width:100%;padding:12px;background:#1a73e8;color:#fff;border:none;border-radius:6px;font-size:1em;cursor:pointer;">
        Save my email
      </button>
      <div id="save-email-message" role="status" style="margin-top:10px;"></div>
    </div>

    <?php if ($error): ?>
      <div class="result error" style="margin-top:16px;background:#fee;padding:12px;border-radius:6px;"><strong>Error:</strong> <?= htmlspecialchars($error, ENT_QUOTES) ?></div>
    <?php elseif ($response): ?>
      <div class="result" style="margin-top:16px;background:#f6f9ff;padding:12px;border-radius:6px;">
        <h3>Response (HTTP <?= htmlspecialchars($response['http_code'], ENT_QUOTES) ?>)</h3>
        <pre style="white-space:pre-wrap;word-break:break-word;"><?= htmlspecialchars(is_array($response['body']) ? json_encode($response['body'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) : $response['body'], ENT_QUOTES) ?></pre>
      </div>
      <?php if ($success_message): ?>
        <div class="result" style="margin-top:12px;background:#e6ffed;padding:12px;border-radius:6px;"><strong><?= htmlspecialchars($success_message, ENT_QUOTES) ?></strong></div>
      <?php endif; ?>
    <?php endif; ?>

    <footer style="margin-top:20px">
      <small>Backend URL: <?= htmlspecialchars($apiUrl, ENT_QUOTES) ?></small>
    </footer>
  </div>

  <script>
  document.addEventListener('DOMContentLoaded', function() {
    const countySelect = document.querySelector('select[name="county"]');
    const cityInputContainer = document.getElementById('city-input-container');
    const cityLabelText = document.getElementById('city-label-text');
    const grantCities = ["corinth", "crittenden", "dry ridge", "williamstown"];

    // previous city from server (lowercased)
    const prevCity = <?= json_encode(strtolower(postval('city', ''))) ?>;

    function renderCityField() {
      const selectedCounty = (countySelect.value || '').trim().toLowerCase();
      if (selectedCounty === 'grant') {
        // Create a dropdown for Grant county cities
        let options = '<option value="" disabled ' + (prevCity === "" ? 'selected' : '') + '>Select a city</option>';
        grantCities.forEach(function(city) {
          const label = city.charAt(0).toUpperCase() + city.slice(1);
          options += `<option value="${city}"${prevCity === city ? ' selected' : ''}>${label}</option>`;
        });
        cityInputContainer.innerHTML = `<select name="city" required style="width:100%;padding:8px;margin-top:6px">${options}</select>`;
        cityLabelText.textContent = "City (required for Grant)";
      } else {
        // Free text input for other counties
        // Keep previously posted city value (if any)
        const val = <?= json_encode(postval('city', '')) ?>;
        cityInputContainer.innerHTML = `<input type="text" name="city" value="${val.replace(/"/g, '&quot;')}" style="width:100%;padding:8px" />`;
        cityLabelText.textContent = "City (optional)";
      }
    }

    countySelect.addEventListener('change', renderCityField);

    // Run on page load to ensure the right city input is present
    renderCityField();
  });
  </script>

<!-- with this (server-side inserts the nonce) -->
<script nonce="<?= htmlspecialchars($nonce, ENT_QUOTES) ?>" src="/static/save_email.js"></script>

  <style>
  /* Optional: visually indicate when city is required for Grant */
  #city-label select[required], #city-label input[required] {
    outline: 2px solid #e53;
  }
  .container input, .container select, .container button { font-family: inherit; }
  </style>
</body>
</html>