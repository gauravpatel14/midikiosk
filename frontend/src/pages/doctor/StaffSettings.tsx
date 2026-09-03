import { useNavigate } from 'react-router-dom'
import { ArrowLeft, User, LogOut, ChevronRight } from 'lucide-react'

export function StaffSettings() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="bg-[#00447C] p-4 text-white flex justify-between items-center shadow-md z-10 sticky top-0">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="p-1 -ml-1">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <div>
            <span className="font-semibold block leading-tight">Staff Profile</span>
            <span className="text-[10px] text-blue-200">Preferences</span>
          </div>
        </div>
        <User className="w-8 h-8 bg-white/20 rounded-full p-1" />
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="bg-white p-6 border-b border-gray-100 flex flex-col items-center mb-6 shadow-sm">
          <div className="w-20 h-20 bg-gray-200 rounded-full mb-3 overflow-hidden border-4 border-[#F8FBFC] shadow-sm">
            <img src="https://images.unsplash.com/photo-1559839734-2b71ea197ec2?ixlib=rb-4.0.3&auto=format&fit=crop&w=200&q=80" alt="Doctor Profile" className="w-full h-full object-cover" />
          </div>
          <h2 className="text-xl font-bold text-[#00447C]">Dr. Priya Sharma</h2>
          <p className="text-sm text-[#008891] font-medium mb-1">Senior Consultant — Ayurveda Dept</p>
          <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-50 px-3 py-1 rounded-full border border-gray-100">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>
            Staff ID: MDK-8834
          </div>
          <p className="text-xs text-gray-400 mt-3">All India Institute of Ayurveda, New Delhi</p>
        </div>

        <div className="px-4 space-y-6 pb-6">
          {/* Notification Preferences */}
          <div>
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 px-2">Notification Preferences</h3>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden divide-y divide-gray-50">
              <div className="p-4 flex justify-between items-center">
                <span className="text-sm font-bold text-gray-700">Critical Triage Alerts</span>
                <div className="w-10 h-5 bg-[#008891] rounded-full relative">
                  <div className="absolute right-1 top-0.5 w-4 h-4 bg-white rounded-full shadow"></div>
                </div>
              </div>
              <div className="p-4 flex justify-between items-center">
                <span className="text-sm font-bold text-gray-700">Patient Queue Updates</span>
                <div className="w-10 h-5 bg-[#008891] rounded-full relative">
                  <div className="absolute right-1 top-0.5 w-4 h-4 bg-white rounded-full shadow"></div>
                </div>
              </div>
              <div className="p-4 flex justify-between items-center">
                <span className="text-sm font-bold text-gray-700">Lab Result Completion</span>
                <div className="w-10 h-5 bg-gray-200 rounded-full relative">
                  <div className="absolute left-1 top-0.5 w-4 h-4 bg-white rounded-full shadow"></div>
                </div>
              </div>
            </div>
          </div>

          {/* Kiosk Preferences */}
          <div>
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 px-2">Kiosk Preferences</h3>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden divide-y divide-gray-50">
              <div className="p-4 flex justify-between items-center cursor-pointer">
                <span className="text-sm font-bold text-gray-700">App Language</span>
                <div className="flex items-center text-sm text-gray-500">
                  English (EN) <ChevronRight className="w-4 h-4 ml-1" />
                </div>
              </div>
              <div className="p-4 flex justify-between items-center">
                <span className="text-sm font-bold text-gray-700">Dark Mode Display</span>
                <div className="w-10 h-5 bg-gray-200 rounded-full relative">
                  <div className="absolute left-1 top-0.5 w-4 h-4 bg-white rounded-full shadow"></div>
                </div>
              </div>
              <div className="p-4 flex justify-between items-center cursor-pointer">
                <span className="text-sm font-bold text-gray-700">Default Department</span>
                <div className="flex items-center text-sm text-gray-500">
                  Ayurveda OPD <ChevronRight className="w-4 h-4 ml-1" />
                </div>
              </div>
              <div className="p-4 flex justify-between items-center">
                <span className="text-sm font-bold text-gray-700">Auto-generate AI Summary</span>
                <div className="w-10 h-5 bg-[#008891] rounded-full relative">
                  <div className="absolute right-1 top-0.5 w-4 h-4 bg-white rounded-full shadow"></div>
                </div>
              </div>
            </div>
          </div>

          {/* About */}
          <div>
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 px-2">About MediKiosk</h3>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden divide-y divide-gray-50">
              <div className="p-4 flex justify-between items-center">
                <span className="text-sm font-bold text-gray-700">System Version</span>
                <span className="text-sm text-gray-500">v2.4.1 (Stable)</span>
              </div>
              <div className="p-4 flex justify-between items-center">
                <span className="text-sm font-bold text-gray-700">ABDM Sandbox Compliance</span>
                <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">VERIFIED</span>
              </div>
            </div>
          </div>

          <button 
            onClick={() => navigate('/role')}
            className="w-full bg-white border border-red-200 text-red-600 py-4 rounded-2xl font-bold text-sm active:scale-95 transition-transform shadow-sm flex items-center justify-center gap-2"
          >
            <LogOut className="w-4 h-4" /> SIGN OUT OF KIOSK
          </button>
          
          <p className="text-center text-[10px] text-gray-400 pb-4">
            You will not receive alerts if you sign out. Remember to lock badge if quick logoff.
          </p>
        </div>
      </div>
    </div>
  )
}
