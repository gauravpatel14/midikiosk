import { useNavigate } from 'react-router-dom'
import { ArrowLeft, User, Activity, FileText } from 'lucide-react'

export function LabResults() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="bg-[#00447C] p-4 text-white flex justify-between items-center shadow-md z-10 sticky top-0">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="p-1 -ml-1">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <span className="font-semibold">Lab Results</span>
        </div>
        <User className="w-8 h-8 bg-white/20 rounded-full p-1" />
      </header>

      <div className="p-4 flex-1 overflow-y-auto">
        <div className="text-xs font-semibold text-[#008891] mb-4 flex items-center gap-2">
          <span className="w-2 h-2 bg-[#008891] rounded-full"></span>
          Active Case: Patient A126 • 62y • Male • PID: 1982
        </div>

        <div className="flex gap-2 mb-6">
          <button className="bg-[#00447C] text-white px-4 py-1.5 rounded-full text-sm font-semibold">Today</button>
          <button className="bg-white text-gray-500 border border-gray-200 px-4 py-1.5 rounded-full text-sm font-semibold">Last 30 Days</button>
          <button className="bg-white text-gray-500 border border-gray-200 px-4 py-1.5 rounded-full text-sm font-semibold">All</button>
        </div>

        <div className="space-y-6">
          {/* CBC Section */}
          <div>
            <h3 className="font-bold text-[#00447C] mb-3">Complete Blood Count (CBC)</h3>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
              {/* High Value */}
              <div className="p-4 border-b border-gray-100 bg-red-50/30">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-bold text-[#00447C] text-sm">White Blood Cells (WBC)</span>
                  <div className="text-right">
                    <span className="font-bold text-red-600 text-lg">14.2</span>
                    <span className="text-xs text-red-500 ml-1 font-medium">x10^3/uL ↑</span>
                  </div>
                </div>
                <div className="flex justify-between items-center text-xs text-gray-500">
                  <span>Ref: 4.5 - 11.0</span>
                  <span className="bg-red-100 text-red-600 px-2 py-0.5 rounded font-bold">HIGH</span>
                </div>
              </div>
              
              {/* Normal Value */}
              <div className="p-4 border-b border-gray-100">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-bold text-gray-700 text-sm">Red Blood Cells (RBC)</span>
                  <div className="text-right">
                    <span className="font-bold text-gray-800 text-lg">4.8</span>
                    <span className="text-xs text-gray-500 ml-1 font-medium">x10^6/uL</span>
                  </div>
                </div>
                <div className="flex justify-between items-center text-xs text-gray-500">
                  <span>Ref: 4.3 - 5.9</span>
                  <span className="bg-[#E5F3F4] text-[#008891] px-2 py-0.5 rounded font-bold">NORMAL</span>
                </div>
              </div>
              
              {/* Low Value */}
              <div className="p-4">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-bold text-gray-700 text-sm">Hemoglobin</span>
                  <div className="text-right">
                    <span className="font-bold text-orange-500 text-lg">13.5</span>
                    <span className="text-xs text-orange-400 ml-1 font-medium">g/dL ↓</span>
                  </div>
                </div>
                <div className="flex justify-between items-center text-xs text-gray-500">
                  <span>Ref: 13.5 - 17.5</span>
                  <span className="bg-orange-50 text-orange-600 px-2 py-0.5 rounded font-bold">LOW</span>
                </div>
              </div>
            </div>
          </div>

          {/* BMP Section */}
          <div>
            <h3 className="font-bold text-[#00447C] mb-3">Basic Metabolic Panel (BMP)</h3>
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="p-4 border-b border-gray-100 bg-red-50/30">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-bold text-[#00447C] text-sm">Glucose, Serum</span>
                  <div className="text-right">
                    <span className="font-bold text-red-600 text-lg">125</span>
                    <span className="text-xs text-red-500 ml-1 font-medium">mg/dL ↑</span>
                  </div>
                </div>
                <div className="flex justify-between items-center text-xs text-gray-500">
                  <span>Ref: 70 - 99</span>
                  <span className="bg-red-100 text-red-600 px-2 py-0.5 rounded font-bold">HIGH</span>
                </div>
              </div>
              
              <div className="p-4">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-bold text-gray-700 text-sm">Creatinine, Serum</span>
                  <div className="text-right">
                    <span className="font-bold text-gray-800 text-lg">0.9</span>
                    <span className="text-xs text-gray-500 ml-1 font-medium">mg/dL</span>
                  </div>
                </div>
                <div className="flex justify-between items-center text-xs text-gray-500">
                  <span>Ref: 0.7 - 1.3</span>
                  <span className="bg-[#E5F3F4] text-[#008891] px-2 py-0.5 rounded font-bold">NORMAL</span>
                </div>
              </div>
            </div>
          </div>

          {/* Pending Investigations */}
          <div>
            <h3 className="font-bold text-[#00447C] mb-3">Pending Investigations (2)</h3>
            <div className="space-y-3">
              <div className="bg-white p-3 rounded-xl border border-orange-200 flex items-center gap-3">
                <div className="bg-orange-50 p-2 rounded-lg text-orange-500">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-gray-700">Urine Routine Analysis</h4>
                  <p className="text-xs text-gray-500">Sent 2 hrs ago • Est. Result in 30 mins</p>
                </div>
              </div>
              <div className="bg-white p-3 rounded-xl border border-orange-200 flex items-center gap-3">
                <div className="bg-orange-50 p-2 rounded-lg text-orange-500">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-gray-700">Abdominal Ultrasound</h4>
                  <p className="text-xs text-gray-500">Scheduled • Awaiting Rad Report</p>
                </div>
              </div>
            </div>
          </div>

        </div>
        
        <div className="mt-8 mb-4">
          <button className="w-full bg-[#00447C] text-white py-3.5 rounded-2xl font-bold active:scale-95 transition-transform shadow-md">
            ORDER NEW INVESTIGATION
          </button>
        </div>
      </div>
    </div>
  )
}
