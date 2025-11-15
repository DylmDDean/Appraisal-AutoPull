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

    // Validate required fields
    if ($address === '') {
        $error = "Address is required.";
    } elseif ($county === '') {
        $error = "County is required.";
    } else {
        $payload = ['address' => $address, 'county' => $county];
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

      <label>City (optional)
        <input type="text" name="city" value="<?= htmlspecialchars($_POST['city'] ?? '') ?>" />
      </label>

      <label>County (required)
        <input type="text" name="county" required value="<?= htmlspecialchars($_POST['county'] ?? '') ?>" />
      </label>

      <label>Property ID (optional)
        <input type="text" name="property_id" value="<?= htmlspecialchars($_POST['property_id'] ?? '') ?>" />
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
</body>
</html>