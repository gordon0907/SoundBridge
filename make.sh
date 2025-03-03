export PYTHONPATH=/opt/homebrew/opt/portaudio/lib:$PYTHONPATH
nuitka --clean-cache=all --standalone --onefile --remove-output --output-dir=dist server.py
mv ./dist/server.bin ./dist/server
