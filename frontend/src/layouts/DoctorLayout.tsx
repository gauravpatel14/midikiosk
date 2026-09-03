import { Outlet, NavLink } from 'react-router-dom'
import { Home, Users, FileText, UserCircle } from 'lucide-react'

export function DoctorLayout() {

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <div className="flex-1 overflow-y-auto pb-20">
        <Outlet />
      </div>
      
      {/* Bottom Navigation */}
      <div className="absolute bottom-0 w-full bg-white border-t border-gray-100 flex justify-around items-center p-3 pb-6 z-50">
        <NavLink 
          to="/doctor/dashboard" 
          className={({ isActive }) => `flex flex-col items-center gap-1 ${isActive ? 'text-[#00447C]' : 'text-gray-400'}`}
        >
          <Home className="w-6 h-6" />
          <span className="text-[10px] font-medium">HOME</span>
        </NavLink>
        
        <NavLink 
          to="/doctor/queue" 
          className={({ isActive }) => `flex flex-col items-center gap-1 ${isActive ? 'text-[#00447C]' : 'text-gray-400'}`}
        >
          <Users className="w-6 h-6" />
          <span className="text-[10px] font-medium">QUEUE</span>
        </NavLink>
        
        <NavLink 
          to="/doctor/prescriptions" 
          className={({ isActive }) => `flex flex-col items-center gap-1 ${isActive ? 'text-[#00447C]' : 'text-gray-400'}`}
        >
          <FileText className="w-6 h-6" />
          <span className="text-[10px] font-medium">DOCS</span>
        </NavLink>
        
        <NavLink 
          to="/doctor/settings" 
          className={({ isActive }) => `flex flex-col items-center gap-1 ${isActive ? 'text-[#00447C]' : 'text-gray-400'}`}
        >
          <UserCircle className="w-6 h-6" />
          <span className="text-[10px] font-medium">STAFF</span>
        </NavLink>
      </div>
    </div>
  )
}
