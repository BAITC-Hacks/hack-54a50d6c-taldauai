// Runs against a real API and local models. Creates synthetic demonstration data.
import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
const base = process.env.ACCEPTANCE_UI_URL || 'http://127.0.0.1:5173'
const artifacts = new URL('../../data/acceptance/', import.meta.url)
await mkdir(artifacts, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
const read = async path => { const response = await page.request.get(`${base}${path}`); assert.equal(response.status(), 200); return response.json() }
const waitFor = async (fn, timeout = 30000) => {
  const end = Date.now() + timeout
  while (Date.now() < end) { const value = await fn(); if (value) return value; await new Promise(resolve => setTimeout(resolve, 1000)) }
  throw new Error('Timed out waiting for acceptance condition')
}
try {
  let id = process.env.ACCEPTANCE_MEETING_ID
  if (!id) {
    await page.goto(`${base}/new`)
    await page.getByLabel('Название совещания').fill('Приёмка: настоящий ML и PostgreSQL')
    await page.locator('#meeting-date').fill('2026-09-23')
    await page.locator('#num-speakers').fill('2')
    await page.locator('input[type=file]').setInputFiles(fileURLToPath(new URL('../../examples/audio/acceptance_mixed.wav', import.meta.url)))
    await page.locator('#consent').click()
    await page.getByRole('button', { name: 'Отправить на обработку' }).click()
    await page.waitForURL('**/meetings/*')
    id = new URL(page.url()).pathname.split('/').pop()
  }
  const path = `/api/meetings/${id}`
  const draft = await waitFor(async () => {
    const meeting = await read(path)
    assert.notEqual(meeting.status, 'failed', meeting.error_message)
    return meeting.status === 'done' && meeting
  }, 900000)
  assert.equal(draft.participants.length, 2)
  assert.ok(draft.segments.length >= 4)
  assert.equal(draft.action_items.length, 2)
  assert.ok(draft.action_items.every(a => a.needs_review))
  await page.goto(`${base}/meetings/${id}`)
  for (const [index, name] of ['Айдана', 'Данияр'].entries()) {
    await page.getByRole('button', { name: `Изменить ${draft.participants[index].name}`, exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.locator('input').nth(0).fill(name)
    await dialog.locator('input').nth(1).fill('Участник')
    await dialog.getByRole('button', { name: 'Сохранить', exact: true }).click()
    await dialog.waitFor({ state: 'hidden' })
  }
  const first = page.getByTestId('action-item').first()
  const fault = async route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Тестовая ошибка сохранения' }) })
  await page.route('**/api/action-items/*', fault)
  await first.getByRole('button', { name: /^Подтвердить(?: поручение)?$/ }).click()
  await page.getByText('Изменение не сохранено', { exact: true }).waitFor()
  assert.equal(await first.getByText('Проверено', { exact: true }).count(), 0)
  assert.ok((await read(path)).action_items[0].needs_review)
  await page.unroute('**/api/action-items/*', fault)
  for (let i = 0; i < 2; i++) {
    const row = page.getByTestId('action-item').nth(i)
    await row.getByRole('button', { name: /^Подтвердить(?: поручение)?$/ }).click()
    await row.getByText('Проверено', { exact: true }).waitFor()
  }
  const originalTask = (await read(path)).action_items[0].task
  await first.getByRole('button', { name: 'Изменить поручение' }).click()
  const edit = page.getByRole('dialog')
  await edit.getByLabel('Суть поручения').fill('Проверить договор и направить замечания')
  await edit.getByLabel('Ответственный', { exact: true }).fill('Внешний юрист')
  await page.route('**/api/action-items/*', fault)
  await edit.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await edit.getByRole('alert').waitFor()
  assert.equal((await read(path)).action_items[0].task, originalTask)
  await page.unroute('**/api/action-items/*', fault)
  await edit.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await edit.waitFor({ state: 'hidden' })
  await first.getByText('Требует проверки', { exact: true }).waitFor()
  assert.equal(await first.getByText('Проверено', { exact: true }).count(), 0)
  const changed = (await read(path)).action_items[0]
  assert.equal(changed.assignee, 'Внешний юрист')
  assert.equal(changed.speaker_label, null)
  assert.equal((await page.request.get(`${base}${path}/export.docx`)).status(), 409)
  await first.getByRole('button', { name: /^Подтвердить(?: поручение)?$/ }).click()
  await first.getByText('Проверено', { exact: true }).waitFor()
  await page.getByRole('button', { name: 'Добавить поручение', exact: true }).click()
  const editor = page.getByRole('dialog')
  await editor.getByLabel('Суть поручения').fill('Ручное поручение: согласовать приложение к договору')
  await editor.getByLabel('Ответственный', { exact: true }).fill('Юридический отдел')
  // Past date makes automatic overdue delivery independent of the demo date.
  await editor.getByLabel('Срок', { exact: true }).fill('2026-01-01')
  await editor.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await editor.waitFor({ state: 'hidden' })
  const manual = page.getByTestId('action-item').filter({ hasText: 'Ручное поручение:' })
  await manual.getByText('Требует проверки', { exact: true }).waitFor()
  await manual.getByRole('button', { name: /^Подтвердить(?: поручение)?$/ }).click()
  await manual.getByText('Проверено', { exact: true }).waitFor()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: /Скачать.*DOCX/ }).click()
  await (await downloadPromise).saveAs(fileURLToPath(new URL('protocol.docx', artifacts)))
  await page.screenshot({ path: fileURLToPath(new URL('review.png', artifacts)), fullPage: true })
  const saved = await read(path)
  const manualTask = saved.action_items.find(a => a.task.startsWith('Ручное поручение:'))
  const notice = await waitFor(async () => (await read('/api/notifications')).find(n => n.action_item_id === manualTask.id), 90000)
  assert.equal(notice.kind, 'overdue')
  await page.goto(`${base}/notifications`)
  const article = page.locator('article').filter({ hasText: 'Ручное поручение:' }).first()
  await article.getByRole('button', { name: 'Прочитано', exact: true }).click()
  await article.getByText('Прочитано', { exact: true }).waitFor()
  await waitFor(async () => (await read('/api/notifications')).find(n => n.id === notice.id)?.read_at)
  await writeFile(new URL('state.json', artifacts), JSON.stringify({ meeting: saved, notification_id: notice.id }, null, 2))
  const badUpload = await page.request.post(`${base}/api/meetings`, { multipart: {
    title: 'Приёмка: повреждённое аудио', date: '2026-09-23', consent_confirmed: 'true',
    file: { name: 'invalid.wav', mimeType: 'audio/wav', buffer: Buffer.from('invalid audio for failure acceptance') },
  } })
  assert.equal(badUpload.status(), 201)
  const badId = (await badUpload.json()).id
  const failed = await waitFor(async () => { const m = await read(`/api/meetings/${badId}`); return m.status === 'failed' && m })
  assert.equal(failed.action_items.length, 0)
  assert.equal(failed.segments.length, 0)
  assert.ok(failed.error_message)
  console.log(JSON.stringify({ passed: true, meeting_id: id, segments: saved.segments.length, ml_tasks: 2, manual_tasks: 1, notification_id: notice.id, artifacts: fileURLToPath(artifacts) }))
} finally { await browser.close() }
