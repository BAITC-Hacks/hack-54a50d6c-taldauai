import type { Meeting } from './types'

const dateOffset = (days: number) => {
  const date = new Date()
  date.setHours(12, 0, 0, 0)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

const meetingDate = (days: number, hours = 10) => {
  const date = new Date()
  date.setDate(date.getDate() + days)
  date.setHours(hours, 0, 0, 0)
  return date.toISOString()
}

export const initialMeetings: Meeting[] = [
  {
    id: 'ops-2026-09',
    title: 'Оперативное совещание по производственным показателям',
    date: meetingDate(-2),
    status: 'Протокол готов',
    summary: 'Рассмотрены производственные показатели за отчётный период, причины отклонений по поставкам сырья и статус инвестиционных проектов. Руководителям блоков поручено усилить претензионную работу, подготовить альтернативы по снабжению и синхронизировать графики с подрядчиками. Отдельно согласованы меры по переаттестации персонала и срокам выставления счетов.',
    participants: [
      { speaker_label: 'SPEAKER_00', name: 'Ерлан Сарсенов', role: 'Заместитель председателя правления', auto_detected: true },
      { speaker_label: 'SPEAKER_01', name: 'Айгуль Нурбаева', role: 'Директор по снабжению', auto_detected: true },
      { speaker_label: 'SPEAKER_02', name: 'Марат Ибраев', role: 'Директор по инвестициям', auto_detected: true },
      { speaker_label: 'SPEAKER_03', name: 'Дана Касымова', role: 'Директор по персоналу', auto_detected: true },
      { speaker_label: 'SPEAKER_04', name: 'Руслан Темирханов', role: 'Финансовый директор', auto_detected: true },
    ],
    segments: [
      { start: 12, end: 28, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Коллеги, начинаем оперативное совещание. Прошу коротко доложить по показателям и отдельно обозначить отклонения, которые требуют решения правления.' },
      { start: 31, end: 52, speaker_label: 'SPEAKER_01', lang: 'mixed', text: 'По снабжению план выполнен на девяносто два процента. Негізгі себеп — поставщик сырья сорвал две поставки, из-за этого образовалось отставание на три дня.' },
      { start: 55, end: 81, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Айгуль, сегодня направьте поставщику официальную претензию за срыв поставок. Параллельно за две недели найдите альтернативного поставщика и представьте сравнительные условия.' },
      { start: 86, end: 103, speaker_label: 'SPEAKER_01', lang: 'kk', text: 'Түсінікті. Бүгін заң қызметімен бірге талап-хатты жібереміз, балама жеткізушілер бойынша нарықты зерттейміз.' },
      { start: 108, end: 128, speaker_label: 'SPEAKER_02', lang: 'ru', text: 'По инвестиционным проектам освоение составляет восемьдесят семь процентов. По двум площадкам подрядчики отстают от календарного графика.' },
      { start: 131, end: 157, speaker_label: 'SPEAKER_00', lang: 'mixed', text: 'На этой неделе проведите совещание со всеми подрядчиками по инвестпроектам. Әр жоба бойынша нақты мерзім керек. По итогам подготовьте справку для правления.' },
      { start: 162, end: 182, speaker_label: 'SPEAKER_03', lang: 'ru', text: 'По охране труда завершили аудит. Для допуска ста двадцати сотрудников требуется внеплановая переаттестация.' },
      { start: 185, end: 202, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Подготовьте смету на переаттестацию персонала по технике безопасности в течение недели. Финансовый блок прошу оперативно согласовать.' },
      { start: 208, end: 225, speaker_label: 'SPEAKER_04', lang: 'ru', text: 'По закрытию месяца есть риск задержки первичных документов от подрядных организаций.' },
      { start: 229, end: 249, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Руслан, уведомите подрядчиков о предельных сроках выставления счетов до конца рабочего дня. Контроль исполнения оставляю за вами.' },
      { start: 254, end: 269, speaker_label: 'SPEAKER_00', lang: 'kk', text: 'Барлық тапсырмалар хаттамаға енгізілсін. Келесі отырыста орындалуын жеке қараймыз.' },
    ],
    action_items: [
      { id: 'a1', meeting_id: 'ops-2026-09', task: 'Направить официальную претензию поставщику сырья за срыв поставок', assignee: 'Айгуль Нурбаева', speaker_label: 'SPEAKER_01', deadline_raw: 'сегодня', deadline_date: dateOffset(-1), status: 'in_progress', urgency: 'high', quote: 'Сегодня направьте поставщику официальную претензию за срыв поставок.', timestamp: 55, reminded_at: null },
      { id: 'a2', meeting_id: 'ops-2026-09', task: 'Найти альтернативного поставщика и представить сравнительные условия', assignee: 'Айгуль Нурбаева', speaker_label: 'SPEAKER_01', deadline_raw: 'за две недели', deadline_date: dateOffset(12), status: 'in_progress', urgency: 'medium', quote: 'За две недели найдите альтернативного поставщика и представьте сравнительные условия.', timestamp: 55, reminded_at: null },
      { id: 'a3', meeting_id: 'ops-2026-09', task: 'Провести совещание с подрядчиками по инвестпроектам и подготовить справку', assignee: 'Марат Ибраев', speaker_label: 'SPEAKER_02', deadline_raw: 'на этой неделе', deadline_date: dateOffset(2), status: 'in_progress', urgency: 'high', quote: 'На этой неделе проведите совещание со всеми подрядчиками по инвестпроектам.', timestamp: 131, reminded_at: null },
      { id: 'a4', meeting_id: 'ops-2026-09', task: 'Подготовить смету на переаттестацию персонала по технике безопасности', assignee: 'Дана Касымова', speaker_label: 'SPEAKER_03', deadline_raw: 'в течение недели', deadline_date: dateOffset(7), status: 'in_progress', urgency: 'medium', quote: 'Подготовьте смету на переаттестацию персонала по технике безопасности в течение недели.', timestamp: 185, reminded_at: null },
      { id: 'a5', meeting_id: 'ops-2026-09', task: 'Уведомить подрядчиков о сроках выставления счетов', assignee: 'Руслан Темирханов', speaker_label: 'SPEAKER_04', deadline_raw: 'до конца рабочего дня', deadline_date: dateOffset(-1), status: 'done', urgency: 'high', quote: 'Уведомите подрядчиков о предельных сроках выставления счетов до конца рабочего дня.', timestamp: 229, reminded_at: null },
    ],
  },
  {
    id: 'budget-committee',
    title: 'Бюджетный комитет: корректировка плана закупок',
    date: meetingDate(-8, 15),
    status: 'Протокол готов',
    summary: 'Комитет согласовал корректировку плана закупок и лимиты на четвёртый квартал. Финансовому блоку поручено обновить прогноз движения денежных средств, закупочному блоку — опубликовать скорректированный план.',
    participants: [
      { speaker_label: 'SPEAKER_00', name: 'Руслан Темирханов', role: 'Финансовый директор', auto_detected: true },
      { speaker_label: 'SPEAKER_01', name: 'Айгуль Нурбаева', role: 'Директор по снабжению', auto_detected: true },
    ],
    segments: [
      { start: 8, end: 28, speaker_label: 'SPEAKER_00', lang: 'ru', text: 'Корректировку лимитов согласовали. До пятницы обновим прогноз движения денежных средств с учётом новых вводных.' },
      { start: 35, end: 55, speaker_label: 'SPEAKER_01', lang: 'ru', text: 'Скорректированный план закупок опубликуем в системе до конца недели и направим инициаторам.' },
    ],
    action_items: [
      { id: 'b1', meeting_id: 'budget-committee', task: 'Обновить прогноз движения денежных средств', assignee: 'Руслан Темирханов', speaker_label: 'SPEAKER_00', deadline_raw: 'до пятницы', deadline_date: dateOffset(-3), status: 'in_progress', urgency: 'high', quote: 'До пятницы обновим прогноз движения денежных средств.', timestamp: 8, reminded_at: new Date(Date.now() - 86_400_000).toISOString() },
      { id: 'b2', meeting_id: 'budget-committee', task: 'Опубликовать скорректированный план закупок', assignee: 'Айгуль Нурбаева', speaker_label: 'SPEAKER_01', deadline_raw: 'до конца недели', deadline_date: dateOffset(-2), status: 'done', urgency: 'low', quote: 'Скорректированный план закупок опубликуем в системе до конца недели.', timestamp: 35, reminded_at: null },
    ],
  },
]
