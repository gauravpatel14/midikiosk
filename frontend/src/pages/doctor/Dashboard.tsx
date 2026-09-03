import { useNavigate } from 'react-router-dom'
import { User, ChevronRight, AlertTriangle } from 'lucide-react'

export function Dashboard() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="bg-[#00447C] p-6 pb-8 text-white rounded-b-3xl shadow-md">
        <div className="flex justify-between items-center mb-6">
          <div className="w-8 h-8 bg-white/20 rounded flex items-center justify-center font-bold">M</div>
          <div className="font-semibold">Clinician Dashboard</div>
          <div className="relative">
            <User className="w-8 h-8 bg-white/20 rounded-full p-1" />
            <div className="absolute top-0 right-0 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-[#00447C]"></div>
          </div>
        </div>
        <h1 className="text-xl font-bold mb-1">Namaste, Dr. Priya</h1>
        <p className="text-blue-200 text-sm">Thursday, 26 Jan 2026 • Morning Session</p>
      </header>

      <div className="px-6 -mt-4 mb-6">
        <div className="bg-white rounded-2xl p-4 shadow-md flex justify-between divide-x divide-gray-100">
          <div className="px-2 text-center flex-1">
            <div className="text-xs text-gray-500 font-medium mb-1">Total Patients</div>
            <div className="text-2xl font-bold text-[#00447C]">18</div>
          </div>
          <div className="px-2 text-center flex-1">
            <div className="text-xs text-gray-500 font-medium mb-1">Waiting</div>
            <div className="text-2xl font-bold text-orange-500">5</div>
          </div>
          <div className="px-2 text-center flex-1">
            <div className="text-xs text-gray-500 font-medium mb-1">Critical</div>
            <div className="text-2xl font-bold text-red-500">2</div>
          </div>
        </div>
      </div>

      <div className="px-6 flex-1 overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-bold text-[#00447C] flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            Critical Attention Required
          </h2>
          <span className="text-xs font-semibold text-red-500 bg-red-50 px-2 py-1 rounded-full">1 Priority</span>
        </div>

        {/* Critical Patient Card */}
        <div className="bg-white border-l-4 border-red-500 rounded-2xl p-4 mb-8 shadow-sm">
          <div className="flex justify-between items-start mb-3">
            <div>
              <h3 className="font-bold text-[#00447C] text-lg">Patient A126</h3>
              <p className="text-sm text-gray-500">Age 62 • M • Wait: 12 min</p>
            </div>
            <span className="text-xs font-bold text-red-500 bg-red-50 px-2 py-1 rounded border border-red-100">CRITICAL</span>
          </div>
          
          <div className="bg-red-50 p-3 rounded-xl mb-4">
            <div className="text-xs text-red-600 font-bold mb-1">Chief Complaint</div>
            <div className="text-sm font-medium text-red-900">Chest pain + severe breathlessness.</div>
          </div>
          
          <div className="flex gap-2 mb-4">
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded font-medium">HR 110 bpm</span>
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded font-medium">SpO2 88%</span>
          </div>
          
          <button 
            onClick={() => navigate('/doctor/patient/A126')}
            className="w-full bg-red-600 text-white font-bold py-3 rounded-xl flex justify-center items-center gap-2 active:scale-95 transition-transform"
          >
            OPEN CLINICAL FILE <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <div className="flex justify-between items-center mb-4">
          <h2 className="font-bold text-[#00447C]">Upcoming Queue</h2>
          <button onClick={() => navigate('/doctor/queue')} className="text-xs font-semibold text-[#008891]">VIEW QUEUE (5) →</button>
        </div>

        {/* Normal Queue items */}
        <div className="space-y-3">
          <div onClick={() => navigate('/doctor/patient/B42')} className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-4 cursor-pointer active:scale-95 transition-transform">
            <div className="w-10 h-10 bg-[#E5F3F4] text-[#008891] rounded-full flex items-center justify-center font-bold">#2</div>
            <div className="flex-1">
              <h4 className="font-bold text-[#00447C]">Patient B42</h4>
              <p className="text-xs text-gray-500 truncate">Follow up checkup after surgery.</p>
              <span className="inline-block mt-1 text-[10px] bg-blue-50 text-[#00447C] px-2 py-0.5 rounded font-bold">ROUTINE</span>
            </div>
            <div className="text-xs text-gray-400 font-medium">5 min wait</div>
          </div>
          
          <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-4 cursor-pointer">
            <div className="w-10 h-10 bg-orange-50 text-orange-500 rounded-full flex items-center justify-center font-bold">#3</div>
            <div className="flex-1">
              <h4 className="font-bold text-[#00447C]">Patient M35</h4>
              <p className="text-xs text-gray-500 truncate">Severe joint pain in knee.</p>
              <span className="inline-block mt-1 text-[10px] bg-orange-50 text-orange-600 px-2 py-0.5 rounded font-bold">URGENT</span>
            </div>
            <div className="text-xs text-gray-400 font-medium">18 min wait</div>
          </div>
        </div>
      </div>
    </div>
  )
}
