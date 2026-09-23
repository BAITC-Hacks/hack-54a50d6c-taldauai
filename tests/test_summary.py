import unittest
from unittest.mock import patch

from ml.summary import summarize_meeting


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.segments = [{'id': 's1', 'text': 'Обсудим обновление договора. Финальная версия документа готова.'}]
        self.tasks = [{'description': 'Проверить договор', 'assignee_name': 'Алия', 'due_date': '2026-09-24'}]
        self.raw = {'context': [{'text': 'Обсуждалось обновление договора.', 'quote': 'Обсудим обновление договора', 'source_segment_ids': ['s1']}],
                    'discussion': [{'text': 'Финальная версия документа уже подготовлена.', 'quote': 'Финальная версия документа готова', 'source_segment_ids': ['s1']}],
                    'decisions': [], 'open_questions': []}

    def test_context_survives_corrected_assignment(self):
        with patch('ml.pipeline._ollama_chat', return_value=self.raw):
            summary, warnings = summarize_meeting(self.segments, self.tasks)
        self.assertIn('Финальная версия документа уже подготовлена.', summary)
        self.assertIn('Алия: Проверить договор', summary)
        self.assertIn('2026-09-24', summary)
        self.assertNotIn('Открытые вопросы', summary)
        self.assertEqual(warnings, [])

    def test_unsupported_claims_are_not_rendered(self):
        self.raw['decisions'] = [{'text': 'Бюджет утверждён.', 'quote': 'Бюджет утверждён на год', 'source_segment_ids': ['s1']}]
        with patch('ml.pipeline._ollama_chat', return_value=self.raw):
            summary, warnings = summarize_meeting(self.segments, self.tasks)
        self.assertNotIn('Бюджет', summary)
        self.assertTrue(warnings)

    def test_model_failure_retains_excerpts_and_tasks(self):
        with patch('ml.pipeline._ollama_chat', side_effect=RuntimeError('offline')):
            summary, warnings = summarize_meeting(self.segments, self.tasks)
        self.assertIn(self.segments[0]['text'], summary)
        self.assertIn('Алия', summary)
        self.assertIn('Выдержки', summary)
        self.assertTrue(warnings)

    def test_late_transcript_fragment_is_included(self):
        segments = self.segments + [{'id': 's2', 'text': 'Обсудим план. ' * 650}, {'id': 's3', 'text': 'Финальное согласование перенесено на следующую встречу.'}]
        tail = {'context': [], 'discussion': [], 'decisions': [{'text': 'Согласование перенесено на следующую встречу.', 'quote': segments[2]['text'], 'source_segment_ids': ['s3']}], 'open_questions': []}
        with patch('ml.pipeline._ollama_chat', side_effect=[self.raw, RuntimeError('offline'), tail]) as call:
            summary, warnings = summarize_meeting(segments, [])
        self.assertEqual(call.call_count, 3)
        self.assertIn('Согласование перенесено', summary)
        self.assertTrue(warnings)

    def test_silence_does_not_invoke_model(self):
        with patch('ml.pipeline._ollama_chat') as model:
            summary, warnings = summarize_meeting([], [])
        model.assert_not_called()
        self.assertIn('не обнаружена речь', summary)
        self.assertEqual(warnings, [])
