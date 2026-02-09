const { app, BrowserWindow, shell } = require('electron');
const fs = require('fs');
const path = require('path');

const BASE_URL = process.env.OXIDUS_BASE_URL || 'http://127.0.0.1:5000';
const RETRY_MS = 1000;
const LOG_PATH = path.resolve(__dirname, '..', 'logs', 'electron_app.log');

let mainWindow = null;

function log(message) {
  try {
    const timestamp = new Date().toISOString();
    fs.mkdirSync(path.dirname(LOG_PATH), { recursive: true });
    fs.appendFileSync(LOG_PATH, `[${timestamp}] ${message}\n`);
  } catch {
    // Ignore logging failures.
  }
}

const LOADING_HTML = `<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <style>
      body { background: #1e1e2e; color: #cdd6f4; font-family: Consolas, monospace; display: flex; height: 100vh; align-items: center; justify-content: center; margin: 0; }
      .box { text-align: center; }
      .title { font-size: 28px; letter-spacing: 2px; color: #a6e3a1; }
      .msg { margin-top: 12px; font-size: 14px; color: #89dceb; }
    </style>
  </head>
  <body>
    <div class="box">
      <div class="title">OXIDUS</div>
      <div class="msg">Loading local server…</div>
      <div class="msg">${BASE_URL}</div>
    </div>
  </body>
</html>`;

function createWindow() {
  log('Creating BrowserWindow');
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 900,
    backgroundColor: '#1e1e2e',
    show: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.setTitle('OXIDUS - Live Chat Interface');
  mainWindow.loadURL(`data:text/html,${encodeURIComponent(LOADING_HTML)}`);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  const loadApp = () => {
    log(`Loading ${BASE_URL}`);
    mainWindow.loadURL(BASE_URL).catch((err) => {
      log(`Load failed: ${err}`);
      setTimeout(loadApp, RETRY_MS);
    });
  };

  mainWindow.webContents.on('did-fail-load', (_event, code, desc) => {
    log(`did-fail-load: ${code} ${desc}`);
    setTimeout(loadApp, RETRY_MS);
  });

  mainWindow.on('closed', () => {
    log('Window closed');
    mainWindow = null;
  });

  loadApp();
}

app.whenReady().then(() => {
  log('Electron app ready');
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  log('All windows closed');
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('render-process-gone', (_event, details) => {
  log(`Render process gone: ${JSON.stringify(details)}`);
});

process.on('uncaughtException', (err) => {
  log(`Uncaught exception: ${err && err.stack ? err.stack : err}`);
});
