import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, User } from 'lucide-react'

export function PatientQueue() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('All')

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="bg-[#00447C] p-4 text-white flex justify-between items-center shadow-md z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-white/20 rounded flex items-center justify-center font-bold">M</div>
          <span className="font-semibold">Patient Queue</span>
        </div>
        <User className="w-8 h-8 bg-white/20 rounded-full p-1" />
      </header>

      <div className="p-4 bg-white border-b border-gray-100">
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          {['All', 'Critical (1)', 'Urgent (2)', 'Routine (2)', 'Review (0)'].map(f => (
            <button 
              key={f} 
              onClick={() => setFilter(f.split(' ')[0])}
              className={`whitespace-nowrap px-4 py-1.5 rounded-full text-sm font-semibold border ${
                filter === f.split(' ')[0] 
                ? 'bg-[#00447C] text-white border-[#00447C]' 
                : 'bg-white text-gray-500 border-gray-200'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        
        <div className="relative mt-2">
          <Search className="w-5 h-5 absolute left-3 top-2.5 text-gray-400" />
          <input 
            type="text" 
            placeholder="Search Token, Patient ID..." 
            className="w-full bg-gray-50 border border-gray-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#008891]/50"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Critical */}
        <div onClick={() => navigate('/doctor/patient/A126')} className="bg-white p-4 rounded-2xl shadow-sm border border-red-200 flex items-start gap-3 cursor-pointer">
          <div className="w-10 h-10 bg-red-50 text-red-500 rounded-full flex items-center justify-center font-bold mt-1">#1</div>
          <div className="flex-1">
            <div className="flex justify-between items-start mb-1">
              <h4 className="font-bold text-[#00447C]">Patient A126</h4>
              <span className="text-[10px] font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded border border-red-100">CRITICAL</span>
            </div>
            <p className="text-xs text-gray-500 mb-2">Age 62 • M • 12 min wait</p>
            <p className="text-sm font-medium text-red-700 bg-red-50 p-2 rounded">Chest pain + breathlessness.</p>
          </div>
        </div>

        {/* Routine */}
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex items-start gap-3">
          <div className="w-10 h-10 bg-[#E5F3F4] text-[#008891] rounded-full flex items-center justify-center font-bold mt-1">#2</div>
          <div className="flex-1">
            <div className="flex justify-between items-start mb-1">
              <h4 className="font-bold text-[#00447C]">Patient B42</h4>
              <span className="text-[10px] font-bold text-[#00447C] bg-blue-50 px-2 py-0.5 rounded">ROUTINE</span>
            </div>
            <p className="text-xs text-gray-500 mb-2">Age 34 • F • 5 min wait</p>
            <p className="text-sm font-medium text-gray-700">Follow up checkup after surgery.</p>
          </div>
        </div>

        {/* Urgent */}
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-orange-200 flex items-start gap-3">
          <div className="w-10 h-10 bg-orange-50 text-orange-500 rounded-full flex items-center justify-center font-bold mt-1">#3</div>
          <div className="flex-1">
            <div className="flex justify-between items-start mb-1">
              <h4 className="font-bold text-[#00447C]">Patient M35</h4>
              <span className="text-[10px] font-bold text-orange-600 bg-orange-50 px-2 py-0.5 rounded border border-orange-100">URGENT</span>
            </div>
            <p className="text-xs text-gray-500 mb-2">Age 45 • M • 18 min wait</p>
            <p className="text-sm font-medium text-gray-700">Severe joint pain in knee.</p>
          </div>
        </div>
        
        {/* Urgent */}
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-orange-200 flex items-start gap-3 opacity-70">
          <div className="w-10 h-10 bg-orange-50 text-orange-500 rounded-full flex items-center justify-center font-bold mt-1">#4</div>
          <div className="flex-1">
            <div className="flex justify-between items-start mb-1">
              <h4 className="font-bold text-[#00447C]">Patient C89</h4>
              <span className="text-[10px] font-bold text-orange-600 bg-orange-50 px-2 py-0.5 rounded border border-orange-100">URGENT</span>
            </div>
            <p className="text-xs text-gray-500 mb-2">Age 28 • M • 22 min wait</p>
            <p className="text-sm font-medium text-gray-700">Mild fever, cough</p>
          </div>
        </div>
      </div>
    </div>
  )
}
