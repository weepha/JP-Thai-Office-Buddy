$emulator = "C:\Users\mdsc0\AppData\Local\Android\Sdk\emulator\emulator.exe"
$adb = "C:\Users\mdsc0\AppData\Local\Android\Sdk\platform-tools\adb.exe"

Write-Host "Starting Emulator..."
Start-Process -FilePath $emulator -ArgumentList "-avd Medium_Phone_API_36.1"

Write-Host "Waiting for device..."
& $adb wait-for-device

Write-Host "Waiting for Android to finish booting (this may take a minute)..."
$booted = $false
while (-not $booted) {
    Start-Sleep -Seconds 3
    $sysBoot = & $adb shell getprop sys.boot_completed 2>$null
    if ($sysBoot -match "1") {
        $booted = $true
    }
}
Write-Host "Android boot completed!"

# Small delay to ensure services are ready
Start-Sleep -Seconds 3

Write-Host "Opening web app in browser..."
& $adb shell am start -a android.intent.action.VIEW -d http://10.0.2.2:5000/
Write-Host "Done!"
