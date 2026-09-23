from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from .database import SessionLocal
from .models import ActionItem, Meeting, Participant, Segment


def date_offset(days: int) -> date:
    return date.today() + timedelta(days=days)


def meeting_date(days: int, hour: int = 10) -> datetime:
    local_now = datetime.now().astimezone()
    return datetime.combine(date.today() + timedelta(days=days), time(hour=hour), tzinfo=local_now.tzinfo)


def operational_meeting() -> Meeting:
    meeting_id = "ops-2026-09"
    return Meeting(
        id=meeting_id,
        title="Оперативное совещание по производственным показателям",
        date=meeting_date(-2),
        status="done",
        summary="Рассмотрены производственные показатели за отчётный период, причины отклонений по поставкам сырья и статус инвестиционных проектов. Руководителям блоков поручено усилить претензионную работу, подготовить альтернативы по снабжению и синхронизировать графики с подрядчиками. Отдельно согласованы меры по переаттестации персонала и срокам выставления счетов.",
        audio_path=None,
        consent_confirmed=True,
        participants=[
            Participant(speaker_label="SPEAKER_00", name="Ерлан Сарсенов", role="Заместитель председателя правления", auto_detected=True),
            Participant(speaker_label="SPEAKER_01", name="Айгуль Нурбаева", role="Директор по снабжению", auto_detected=True),
            Participant(speaker_label="SPEAKER_02", name="Марат Ибраев", role="Директор по инвестициям", auto_detected=True),
            Participant(speaker_label="SPEAKER_03", name="Дана Касымова", role="Директор по персоналу", auto_detected=True),
            Participant(speaker_label="SPEAKER_04", name="Руслан Темирханов", role="Финансовый директор", auto_detected=True),
        ],
        segments=[
            Segment(start=12, end=28, speaker_label="SPEAKER_00", lang="ru", text="Коллеги, начинаем оперативное совещание. Прошу коротко доложить по показателям и отдельно обозначить отклонения, которые требуют решения правления."),
            Segment(start=31, end=52, speaker_label="SPEAKER_01", lang="mixed", text="По снабжению план выполнен на девяносто два процента. Негізгі себеп — поставщик сырья сорвал две поставки, из-за этого образовалось отставание на три дня."),
            Segment(start=55, end=81, speaker_label="SPEAKER_00", lang="ru", text="Айгуль, сегодня направьте поставщику официальную претензию за срыв поставок. Параллельно за две недели найдите альтернативного поставщика и представьте сравнительные условия."),
            Segment(start=86, end=103, speaker_label="SPEAKER_01", lang="kk", text="Түсінікті. Бүгін заң қызметімен бірге талап-хатты жібереміз, балама жеткізушілер бойынша нарықты зерттейміз."),
            Segment(start=108, end=128, speaker_label="SPEAKER_02", lang="ru", text="По инвестиционным проектам освоение составляет восемьдесят семь процентов. По двум площадкам подрядчики отстают от календарного графика."),
            Segment(start=131, end=157, speaker_label="SPEAKER_00", lang="mixed", text="На этой неделе проведите совещание со всеми подрядчиками по инвестпроектам. Әр жоба бойынша нақты мерзім керек. По итогам подготовьте справку для правления."),
            Segment(start=162, end=182, speaker_label="SPEAKER_03", lang="ru", text="По охране труда завершили аудит. Для допуска ста двадцати сотрудников требуется внеплановая переаттестация."),
            Segment(start=185, end=202, speaker_label="SPEAKER_00", lang="ru", text="Подготовьте смету на переаттестацию персонала по технике безопасности в течение недели. Финансовый блок прошу оперативно согласовать."),
            Segment(start=208, end=225, speaker_label="SPEAKER_04", lang="ru", text="По закрытию месяца есть риск задержки первичных документов от подрядных организаций."),
            Segment(start=229, end=249, speaker_label="SPEAKER_00", lang="ru", text="Руслан, уведомите подрядчиков о предельных сроках выставления счетов до конца рабочего дня. Контроль исполнения оставляю за вами."),
            Segment(start=254, end=269, speaker_label="SPEAKER_00", lang="kk", text="Барлық тапсырмалар хаттамаға енгізілсін. Келесі отырыста орындалуын жеке қараймыз."),
        ],
        action_items=[
            ActionItem(id="a1", task="Направить официальную претензию поставщику сырья за срыв поставок", assignee="Айгуль Нурбаева", speaker_label="SPEAKER_01", deadline_raw="сегодня", deadline_date=date_offset(-1), status="in_progress", urgency="high", quote="Сегодня направьте поставщику официальную претензию за срыв поставок.", timestamp=55, needs_review=False, reminded_at=None),
            ActionItem(id="a2", task="Найти альтернативного поставщика и представить сравнительные условия", assignee="Айгуль Нурбаева", speaker_label="SPEAKER_01", deadline_raw="за две недели", deadline_date=date_offset(12), status="in_progress", urgency="medium", quote="За две недели найдите альтернативного поставщика и представьте сравнительные условия.", timestamp=55, needs_review=False, reminded_at=None),
            ActionItem(id="a3", task="Провести совещание с подрядчиками по инвестпроектам и подготовить справку", assignee="Марат Ибраев", speaker_label="SPEAKER_02", deadline_raw="на этой неделе", deadline_date=date_offset(2), status="in_progress", urgency="high", quote="На этой неделе проведите совещание со всеми подрядчиками по инвестпроектам.", timestamp=131, needs_review=False, reminded_at=None),
            ActionItem(id="a4", task="Подготовить смету на переаттестацию персонала по технике безопасности", assignee="Дана Касымова", speaker_label="SPEAKER_03", deadline_raw="в течение недели", deadline_date=date_offset(7), status="in_progress", urgency="medium", quote="Подготовьте смету на переаттестацию персонала по технике безопасности в течение недели.", timestamp=185, needs_review=False, reminded_at=None),
            ActionItem(id="a5", task="Уведомить подрядчиков о сроках выставления счетов", assignee="Руслан Темирханов", speaker_label="SPEAKER_04", deadline_raw="до конца рабочего дня", deadline_date=date_offset(-1), status="done", urgency="high", quote="Уведомите подрядчиков о предельных сроках выставления счетов до конца рабочего дня.", timestamp=229, needs_review=False, reminded_at=None),
        ],
    )


def budget_meeting() -> Meeting:
    meeting_id = "budget-committee"
    return Meeting(
        id=meeting_id,
        title="Бюджетный комитет: корректировка плана закупок",
        date=meeting_date(-8, 15),
        status="done",
        summary="Комитет согласовал корректировку плана закупок и лимиты на четвёртый квартал. Финансовому блоку поручено обновить прогноз движения денежных средств, закупочному блоку — опубликовать скорректированный план.",
        audio_path=None,
        consent_confirmed=True,
        participants=[
            Participant(speaker_label="SPEAKER_00", name="Руслан Темирханов", role="Финансовый директор", auto_detected=True),
            Participant(speaker_label="SPEAKER_01", name="Айгуль Нурбаева", role="Директор по снабжению", auto_detected=True),
        ],
        segments=[
            Segment(start=8, end=28, speaker_label="SPEAKER_00", lang="ru", text="Корректировку лимитов согласовали. До пятницы обновим прогноз движения денежных средств с учётом новых вводных."),
            Segment(start=35, end=55, speaker_label="SPEAKER_01", lang="ru", text="Скорректированный план закупок опубликуем в системе до конца недели и направим инициаторам."),
        ],
        action_items=[
            ActionItem(id="b1", task="Обновить прогноз движения денежных средств", assignee="Руслан Темирханов", speaker_label="SPEAKER_00", deadline_raw="до пятницы", deadline_date=date_offset(-3), status="in_progress", urgency="high", quote="До пятницы обновим прогноз движения денежных средств.", timestamp=8, needs_review=False, reminded_at=datetime.now().astimezone() - timedelta(days=1)),
            ActionItem(id="b2", task="Опубликовать скорректированный план закупок", assignee="Айгуль Нурбаева", speaker_label="SPEAKER_01", deadline_raw="до конца недели", deadline_date=date_offset(-2), status="done", urgency="low", quote="Скорректированный план закупок опубликуем в системе до конца недели.", timestamp=35, needs_review=False, reminded_at=None),
        ],
    )


def main() -> None:
    seeded = 0
    with SessionLocal() as session:
        for meeting in (operational_meeting(), budget_meeting()):
            if session.scalar(select(Meeting.id).where(Meeting.id == meeting.id)) is None:
                session.add(meeting)
                seeded += 1
        session.commit()
    print(f"Seed complete: added {seeded} meeting(s).")


if __name__ == "__main__":
    main()
