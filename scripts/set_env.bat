:: set-nullkey.bat
:: This script sets the NULLKEY environment variable to "nullkey"

@echo off

:: Set for current session
set NULLKEY=nullkey
echo NULLKEY is set to: %NULLKEY%

:: (Optional) Make it persistent for the user
:: Uncomment the next line if you want it permanent
:: setx NULLKEY "nullkey"
