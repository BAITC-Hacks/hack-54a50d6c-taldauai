import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { MeetingsPage } from './pages/MeetingsPage'
import { NewMeetingPage } from './pages/NewMeetingPage'
import { MeetingPage } from './pages/MeetingPage'
import { TasksPage } from './pages/TasksPage'

export default function App() {
  return <Layout><Routes>
    <Route path="/" element={<MeetingsPage />} />
    <Route path="/new" element={<NewMeetingPage />} />
    <Route path="/meetings/:id" element={<MeetingPage />} />
    <Route path="/tasks" element={<TasksPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Layout>
}
