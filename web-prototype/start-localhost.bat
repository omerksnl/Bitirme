@echo off
cd /d "C:\Users\EXCALIBUR\OneDrive\Documents\ChatGPT\Bitirme Projesi\web-prototype"
if not exist node_modules call npm install
call npm run dev -- --host 127.0.0.1
pause
