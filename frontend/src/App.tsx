import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import DashboardPage from './app/routes/DashboardPage'
import GeneralScenarioPage from './app/routes/GeneralScenarioPage'
import AlertsPage from './app/routes/AlertsPage'
import AgentPage from './app/routes/AgentPage'
import SettingsPage from './app/routes/SettingsPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true,              element: <DashboardPage /> },
      { path: 'cenario-geral',    element: <GeneralScenarioPage /> },
      { path: 'alertas',          element: <AlertsPage /> },
      { path: 'agent-ia',         element: <AgentPage /> },
      { path: 'configuracoes',    element: <SettingsPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
