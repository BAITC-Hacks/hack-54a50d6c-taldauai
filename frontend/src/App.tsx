import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LandingPage } from './pages/LandingPage'
import { MeetingsPage } from './pages/MeetingsPage'
import { NewMeetingPage } from './pages/NewMeetingPage'
import { LiveMeetingPage } from './pages/LiveMeetingPage'
import { MeetingPage } from './pages/MeetingPage'
import { TasksPage } from './pages/TasksPage'

function LegacyMeetingRedirect() {
  const { id } = useParams()
  return <Navigate to={`/app/meetings/${encodeURIComponent(id ?? '')}`} replace />
}

export default function App() {
  return <Routes>
    <Route path="/" element={<LandingPage />} />
    <Route path="/app" element={<Layout />}>
      <Route index element={<MeetingsPage />} />
      <Route path="new" element={<NewMeetingPage />} />
      <Route path="live" element={<LiveMeetingPage />} />
      <Route path="meetings/:id" element={<MeetingPage />} />
      <Route path="tasks" element={<TasksPage />} />
    </Route>
    <Route path="/new" element={<Navigate to="/app/new" replace />} />
    <Route path="/live" element={<Navigate to="/app/live" replace />} />
    <Route path="/meetings/:id" element={<LegacyMeetingRedirect />} />
    <Route path="/tasks" element={<Navigate to="/app/tasks" replace />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
