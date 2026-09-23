// Browser capture controls; uses Chromium's synthetic microphone, no real microphone.
import { chromium } from 'playwright'
import assert from 'node:assert/strict'
const base = process.env.ACCEPTANCE_UI_URL || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })
const context = await browser.newContext({ permissions: ['microphone'], viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
const errors = []
page.on('pageerror', error => errors.push(error.message))
try {
  await page.goto(`${base}/live`)
  const start = page.getByRole('button', { name: 'Начать созвон', exact: true })
  assert.ok(await start.isDisabled())
  await page.getByLabel('Название встречи', { exact: true }).fill('Тест браузерной записи')
  await page.locator('#meeting-consent').click()
  await page.getByRole('button', { name: 'Только микрофон', exact: true }).click()
  await start.click()
  await page.getByRole('button', { name: 'Завершить созвон', exact: true }).waitFor()
  await page.waitForTimeout(1500) // collect a real MediaRecorder chunk
  await page.getByRole('button', { name: 'Пауза', exact: true }).click()
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click()
  await page.getByRole('button', { name: 'Завершить созвон', exact: true }).click()
  await page.getByLabel('Прослушать запись встречи').waitFor()
  let uploads = 0
  await page.route('**/api/meetings', async route => {
    if (route.request().method() !== 'POST') return route.continue()
    uploads += 1
    const body = route.request().postDataBuffer()
    assert.ok(body && body.length > 1000)
    assert.ok(body.includes(Buffer.from('consent_confirmed')))
    assert.ok(body.includes(Buffer.from('audio/webm')) || body.includes(Buffer.from('audio/mp4')))
    await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Тестовый отказ загрузки"}' })
  })
  await page.getByRole('button', { name: 'Подготовить стенограмму', exact: true }).click()
  await page.getByRole('alert').waitFor()
  assert.equal(uploads, 1)
  assert.ok(await page.getByLabel('Прослушать запись встречи').isVisible())
  assert.ok(await page.getByRole('button', { name: 'Подготовить стенограмму', exact: true }).isEnabled())
  assert.deepEqual(errors, [])
  await page.goto(`${base}/live`)
  await page.evaluate(() => {
    navigator.mediaDevices.getDisplayMedia = async () => {
      const canvas = document.createElement('canvas')
      return canvas.captureStream() // video only: explicitly missing tab audio
    }
  })
  await page.getByLabel('Название встречи', { exact: true }).fill('Вкладка без аудио')
  await page.locator('#meeting-consent').click()
  await start.click()
  await page.getByText('Вкладка передана без звука.', { exact: false }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Завершить созвон', exact: true }).count(), 0)
  console.log('PASS: consent gate, microphone capture, pause/resume, preview, upload failure/retry and tab without audio. OS tab selection is not tested.')
} finally { await browser.close() }
