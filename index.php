<?php
// public/index.php
// PHP front-end: server-side POST to Flask backend using cURL and show JSON response.
// County is now required.

$apiUrl = getenv('FLASK_API_URL') ?: "http://localhost:5000/api/send-requests";

$response = null;
$error = null;
$success_message = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $address = trim($_POST['address'] ?? '');
    $city = trim($_POST['city'] ?? '');
    $county = trim($_POST['county'] ?? '');
    $property_id = trim($_POST['property_id'] ?? '');
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
            }
        }
        curl_close($ch);
    }
}
?>
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Send Requests — PHP Frontend</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <h1>Send Requests</h1>

    <form method="post" novalidate>
      <label>Address (required)
        <input type="text" name="address" required value="<?= htmlspecialchars($_POST['address'] ?? '') ?>" />
      </label>

      <label id="city-label">
        City (optional)
        <span id="city-input-container">
          <input type="text" name="city" value="<?= htmlspecialchars($_POST['city'] ?? '') ?>" />
        </span>
      </label>

      <label>County (required)
        <select name="county" required>
          <option value="" disabled <?= empty($_POST['county']) ? 'selected' : '' ?>>Select a county</option>
          <option value="anderson " <?= (isset($_POST['county']) && $_POST['county'] == 'anderson ') ? 'selected' : '' ?>>anderson </option>
          <option value="boone" <?= (isset($_POST['county']) && $_POST['county'] == 'boone') ? 'selected' : '' ?>>boone</option>
          <option value="carroll" <?= (isset($_POST['county']) && $_POST['county'] == 'carroll') ? 'selected' : '' ?>>carroll</option>
          <option value="franklin" <?= (isset($_POST['county']) && $_POST['county'] == 'franklin') ? 'selected' : '' ?>>franklin</option>
          <option value="gallatin" <?= (isset($_POST['county']) && $_POST['county'] == 'gallatin') ? 'selected' : '' ?>>gallatin</option>
          <option value="grant" <?= (isset($_POST['county']) && $_POST['county'] == 'grant') ? 'selected' : '' ?>>grant</option>
          <option value="kenton" <?= (isset($_POST['county']) && $_POST['county'] == 'kenton') ? 'selected' : '' ?>>kenton</option>
          <option value="owen" <?= (isset($_POST['county']) && $_POST['county'] == 'owen') ? 'selected' : '' ?>>owen</option>
          <option value="scott" <?= (isset($_POST['county']) && $_POST['county'] == 'scott') ? 'selected' : '' ?>>scott</option>
          <option value="trimble" <?= (isset($_POST['county']) && $_POST['county'] == 'trimble') ? 'selected' : '' ?>>trimble</option>
          <!-- Add other counties as needed -->
        </select>
      </label>

      <!-- Send checkboxes -->
      <label>
        <input type="checkbox" name="send_to_pva" <?= (isset($_POST['send_to_pva']) ? 'checked' : 'checked') ?> />
        Send to PVA
      </label>
      <label>
        <input type="checkbox" name="send_to_zoning" <?= (isset($_POST['send_to_zoning']) ? 'checked' : 'checked') ?> />
        Send to Zoning
      </label>

      <div class="actions">
        <button type="submit">Send</button>
        <a class="btn-ghost" href="index.html">Try AJAX front-end</a>
      </div>
    </form>

    <?php if ($error): ?>
      <div class="result error"><strong>Error:</strong> <?= htmlspecialchars($error) ?></div>
    <?php elseif ($response): ?>
      <div class="result">
        <h3>Response (HTTP <?= htmlspecialchars($response['http_code']) ?>)</h3>
        <pre><?= htmlspecialchars(json_encode($response['body'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) ?></pre>
      </div>
      <?php if ($success_message): ?>
        <div class="result"><strong><?= htmlspecialchars($success_message) ?></strong></div>
      <?php endif; ?>
    <?php endif; ?>

    <footer>
      <small>Backend URL: <?= htmlspecialchars($apiUrl) ?></small>
    </footer>
  </div>

  <script>
  document.addEventListener('DOMContentLoaded', function() {
    const countySelect = document.querySelector('select[name="county"]');
    const cityInputContainer = document.getElementById('city-input-container');
    const grantCities = ["corinth", "crittenden", "dry ridge", "williamstown"];

    function renderCityField() {
      const selectedCounty = countySelect.value.trim().toLowerCase();
      const prevCity = <?= json_encode($_POST['city'] ?? '') ?>.toLowerCase();
      if (selectedCounty === 'grant') {
        // Create a dropdown for cities
        let options = '<option value="" disabled ' + (prevCity === "" ? 'selected' : '') + '>Select a city</option>';
        grantCities.forEach(function(city) {
          const label = city.charAt(0).toUpperCase() + city.slice(1);
          options += `<option value="${city}"${prevCity === city ? ' selected' : ''}>${label}</option>`;
        });
        cityInputContainer.innerHTML = `<select name="city" required>${options}</select>`;
        document.getElementById('city-label').childNodes[0].textContent = "City (required for Grant)";
      } else {
        // Free text input for other counties
        cityInputContainer.innerHTML = `<input type="text" name="city" value="<?= htmlspecialchars($_POST['city'] ?? '') ?>" />`;
        document.getElementById('city-label').childNodes[0].textContent = "City (optional)";
      }
    }

    countySelect.addEventListener('change', renderCityField);

    // Run on page load
    renderCityField();
  });
  </script>

  <style>
  /* Optional: visually indicate when city is required for Grant */
  #city-label select[required], #city-label input[required] {
    border-color: #e53;
  }
  </style>
</body>
</html>