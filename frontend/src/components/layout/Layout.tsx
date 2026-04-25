import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import TopBar  from './TopBar'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bg-base">
      <Sidebar />
      <TopBar />
      <main className="pl-[220px] pt-[56px]">
        <div className="page-enter min-h-[calc(100vh-56px)] p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
