const { chromium } = require('/usr/lib/node_modules/playwright');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

(async () => {
  const browser = await chromium.launch({
    executablePath: '/usr/bin/chromium',
    args: ['--allow-file-access-from-files'],
    headless: true
  });
  
  const page = await browser.newPage();
  
  // Set viewport to capture nicely
  await page.setViewportSize({ width: 1024, height: 768 });
  
  // Stub WebSocket to prevent connections
  await page.addInitScript(() => {
    window.WebSocket = class MockWebSocket {
      constructor(url) {
        this.url = url;
        this.readyState = 1; // OPEN
      }
      send(data) {}
      close() {}
    };
  });
  
  const htmlPath = 'file://' + path.resolve(__dirname, '../index.html');
  console.log('Loading page:', htmlPath);
  await page.goto(htmlPath);
  
  // Go to Lighting tab
  await page.click('text=Lighting');
  
  // Click on "Equalizer" effect chip
  await page.click('text=Equalizer');
  
  // Wait a bit for transition
  await page.waitForTimeout(500);
  
  // Prepare temp directory for frames
  const tempDir = path.resolve(__dirname, 'gif_frames');
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir);
  }
  
  console.log('Capturing frames...');
  const element = await page.$('#ledPreview');
  
  const numFrames = 30;
  const delayMs = 50; // 50ms interval = 20fps
  
  for (let i = 0; i < numFrames; i++) {
    const framePath = path.join(tempDir, `frame_${String(i).padStart(3, '0')}.png`);
    await element.screenshot({ path: framePath });
    await page.waitForTimeout(delayMs);
  }
  
  await browser.close();
  
  console.log('Compiling frames with ImageMagick convert...');
  const outputGif = path.resolve(__dirname, '../../docs/images/led-effect-equalizer.gif');
  
  // delay 5 is 5/100 of a second = 50ms per frame. loop 0 means infinite loop.
  execSync(`convert -delay 5 -loop 0 ${path.join(tempDir, 'frame_*.png')} ${outputGif}`);
  
  console.log('GIF generated successfully at:', outputGif);
  
  // Clean up frames
  fs.readdirSync(tempDir).forEach(file => {
    fs.unlinkSync(path.join(tempDir, file));
  });
  fs.rmdirSync(tempDir);
  console.log('Cleaned up temporary frames.');
})();
