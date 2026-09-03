import { useNavigate } from 'react-router-dom'
import { useIntakeStore } from '../store/useIntakeStore'
import { ArrowLeft, Stethoscope, Pill, Syringe } from 'lucide-react'

export function Department() {
  const navigate = useNavigate()
  const setDepartment = useIntakeStore(state => state.setDepartment)

  const handleSelect = (dept: string) => {
    setDepartment(dept)
    navigate('/triage')
  }

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="p-6 flex items-center justify-between border-b border-gray-100 bg-white">
        <div className="flex items-center">
          <button onClick={() => navigate(-1)} className="p-2 -ml-2 text-gray-500">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-xl font-bold text-[#00447C] ml-2">Patient Welcome</h1>
        </div>
      </header>

      <div className="p-8 flex-1 overflow-y-auto">
        <div className="bg-[#00447C] text-white p-5 rounded-2xl mb-8 flex justify-between items-center shadow-lg">
          <div>
            <div className="text-xs text-blue-200 font-medium uppercase tracking-wider mb-1">Current Facility</div>
            <div className="font-bold text-lg">All India Institute of Ayurveda</div>
            <div className="text-sm text-blue-100">New Delhi Campus</div>
          </div>
          <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center">
            <div className="w-4 h-4 bg-white rounded-full"></div>
          </div>
        </div>
        
        <h2 className="text-2xl font-bold text-[#00447C] text-center mb-2">Where are you visiting today?</h2>
        <p className="text-gray-500 text-center text-sm mb-8 px-4">
          Select the department you need to visit.
        </p>

        <div className="space-y-4">
          <button 
            onClick={() => handleSelect('Ayurveda OPD')}
            className="w-full bg-[#E5F3F4] border-2 border-[#008891] p-5 rounded-2xl flex items-center justify-between transition-transform active:scale-95"
          >
            <div className="flex items-center gap-4">
              <div className="bg-white p-3 rounded-full text-[#008891]">
                <Stethoscope className="w-6 h-6" />
              </div>
              <div className="text-left">
                <h3 className="font-bold text-[#008891] text-lg">Ayurveda OPD</h3>
                <p className="text-xs text-[#006670] mt-1">Holistic treatment, Panchakarma, and traditional wellness therapies.</p>
              </div>
            </div>
            <span className="text-[#008891] font-bold">→</span>
          </button>

          <button 
            onClick={() => handleSelect('General OPD')}
            className="w-full bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex items-center justify-between transition-transform active:scale-95"
          >
            <div className="flex items-center gap-4">
              <div className="bg-gray-50 p-3 rounded-full text-[#00447C]">
                <Syringe className="w-6 h-6" />
              </div>
              <div className="text-left">
                <h3 className="font-bold text-[#00447C]">General OPD</h3>
                <p className="text-xs text-gray-500 mt-1">Standard medical consultation and diagnostics.</p>
              </div>
            </div>
            <span className="text-gray-300 font-bold">›</span>
          </button>

          <button 
            onClick={() => handleSelect('Other')}
            className="w-full bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex items-center justify-between transition-transform active:scale-95"
          >
            <div className="flex items-center gap-4">
              <div className="bg-gray-50 p-3 rounded-full text-[#00447C]">
                <Pill className="w-6 h-6" />
              </div>
              <div className="text-left">
                <h3 className="font-bold text-[#00447C]">Other Departments</h3>
                <p className="text-xs text-gray-500 mt-1">Pharmacy, Billing, and Administration.</p>
              </div>
            </div>
            <span className="text-gray-300 font-bold">›</span>
          </button>
        </div>
      </div>
      
      <div className="p-6 text-center text-[#00447C] bg-white border-t border-gray-100">
        <div className="w-14 h-14 mx-auto bg-[#00447C] text-white rounded-full flex items-center justify-center mb-2 shadow-lg">
          <Stethoscope className="w-6 h-6" />
        </div>
        <span className="text-sm font-bold">Tap to speak</span>
      </div>
    </div>
  )
}
