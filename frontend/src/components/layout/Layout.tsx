import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar  from './TopBar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-bg-base">
      <Sidebar />
      <TopBar />
      <main className="pl-[220px] pt-[56px]">
        <div className="page-enter min-h-[calc(100vh-56px)] p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
