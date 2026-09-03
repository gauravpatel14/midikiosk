import { useNavigate } from 'react-router-dom'
import { ArrowLeft, User, ClipboardList, CheckCircle2 } from 'lucide-react'

export function ShiftHandoff() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="bg-[#00447C] p-4 text-white flex justify-between items-center shadow-md z-10 sticky top-0">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="p-1 -ml-1">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <span className="font-semibold">Shift Handoff</span>
        </div>
        <User className="w-8 h-8 bg-white/20 rounded-full p-1" />
      </header>

      <div className="p-4 flex-1 overflow-y-auto">
        <div className="bg-[#00447C] text-white rounded-2xl p-5 mb-6 shadow-md relative overflow-hidden">
          <div className="absolute -right-4 -top-4 opacity-10">
            <ClipboardList className="w-32 h-32" />
          </div>
          <div className="flex justify-between items-start mb-4 relative z-10">
            <div>
              <h2 className="font-bold text-lg">Morning Shift Summary</h2>
              <p className="text-xs text-blue-200 mt-1">Thursday, 26 Jan 2026 • 08:00 AM - 2:00 PM</p>
            </div>
            <span className="bg-emerald-500 text-white text-[10px] font-bold px-2 py-1 rounded">ACTIVE</span>
          </div>
          
          <div className="flex divide-x divide-white/20 bg-black/20 rounded-xl p-3 relative z-10">
            <div className="flex-1 text-center">
              <div className="text-xs text-blue-200">Total Seen</div>
              <div className="text-xl font-bold">14</div>
            </div>
            <div className="flex-1 text-center">
              <div className="text-xs text-blue-200">Admitted</div>
              <div className="text-xl font-bold">4</div>
            </div>
            <div className="flex-1 text-center">
              <div className="text-xs text-blue-200">Pending</div>
              <div className="text-xl font-bold">2</div>
            </div>
          </div>
        </div>

        <h3 className="font-bold text-[#00447C] mb-3">Patients Requiring Handoff (2)</h3>
        
        <div className="space-y-4 mb-6">
          <div className="bg-white p-4 rounded-2xl shadow-sm border border-red-200">
            <div className="flex justify-between items-start mb-2">
              <div>
                <h4 className="font-bold text-[#00447C]">Patient A126</h4>
                <p className="text-xs text-gray-500">Room 302 • 62y Male</p>
              </div>
              <span className="text-[10px] font-bold text-red-500 bg-red-50 px-2 py-1 rounded border border-red-100">CRITICAL</span>
            </div>
            <p className="text-xs text-gray-600 bg-gray-50 p-2 rounded mb-3">
              Chest pain -&gt; suspected STEMI. Waiting on Trop-I results. ECG done, consulting cardiology. Keep on monitor.
            </p>
            <div className="flex justify-between items-center text-xs">
              <span className="text-orange-500 font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500"></span> Ready for Transfer
              </span>
              <button className="text-gray-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4" /> Reviewed
              </button>
            </div>
          </div>

          <div className="bg-white p-4 rounded-2xl shadow-sm border border-orange-200">
            <div className="flex justify-between items-start mb-2">
              <div>
                <h4 className="font-bold text-[#00447C]">Patient M35</h4>
                <p className="text-xs text-gray-500">Wait Area • 45y Male</p>
              </div>
              <span className="text-[10px] font-bold text-orange-600 bg-orange-50 px-2 py-1 rounded border border-orange-100">PENDING</span>
            </div>
            <p className="text-xs text-gray-600 bg-gray-50 p-2 rounded mb-3">
              Severe joint pain, waiting for X-ray report. Needs ortho consult if fracture confirmed.
            </p>
            <div className="flex justify-between items-center text-xs">
              <span className="text-orange-500 font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500"></span> Needs Follow-up
              </span>
              <button className="text-gray-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4" /> Reviewed
              </button>
            </div>
          </div>
        </div>

        <h3 className="font-bold text-[#00447C] mb-3">General Shift Notes</h3>
        <textarea 
          className="w-full bg-white border border-gray-200 rounded-xl p-3 text-sm text-gray-700 min-h-[100px] mb-6 focus:outline-none focus:ring-2 focus:ring-[#008891]/50 shadow-sm"
          defaultValue="OPD is slightly crowded. Calibration is scheduled for USG Machine 2 at 4:00 PM today. Patient A126 needs priority bed allocation on ward shifting."
        />

        <div className="bg-[#E5F3F4] rounded-2xl p-4 border border-[#008891]/30 mb-8">
          <div className="flex justify-between items-center mb-2">
            <h4 className="font-bold text-[#00447C] text-sm">AI Daily Brief Summary</h4>
            <div className="w-8 h-4 bg-[#008891] rounded-full relative">
              <div className="absolute right-1 top-0.5 w-3 h-3 bg-white rounded-full"></div>
            </div>
          </div>
          <p className="text-xs text-gray-600 leading-relaxed">
            Morning session concluded with 14 discharges and 4 active ward handoffs. Ward 3 capacity is at 90%. Focus has been acute medical about Patient A126 priority vitals.
          </p>
        </div>
        
        <button className="w-full bg-[#00447C] text-white py-4 rounded-2xl font-bold text-lg active:scale-95 transition-transform shadow-md mb-4">
          COMPLETE HANDOFF & SIGN OUT
        </button>
      </div>
    </div>
  )
}
