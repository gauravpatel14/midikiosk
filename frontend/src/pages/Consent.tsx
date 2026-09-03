import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ShieldCheck, FileCheck, CheckSquare, Square } from 'lucide-react'

export function Consent() {
  const navigate = useNavigate()
  const [agreed, setAgreed] = useState(false)

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

      <div className="p-6 flex-1 overflow-y-auto">
        <div className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 mb-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-[#E5F3F4] rounded-bl-full -mr-10 -mt-10 opacity-50"></div>
          <div className="flex items-start gap-4 relative z-10">
            <div className="bg-[#008891] p-3 rounded-full text-white shrink-0 mt-1 shadow-md">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#00447C] mb-2 leading-tight">We will ask you questions about your health.</h2>
              <p className="text-sm text-gray-600 mb-4 leading-relaxed">
                MediKiosk will ask about your health, medicines, allergies, and previous medical records.
                Your information is shared with your doctor only with your permission.
              </p>
              <button className="bg-[#E5F3F4] text-[#008891] px-4 py-2 rounded-full text-sm font-bold flex items-center gap-2">
                🔊 Listen to this explanation
              </button>
            </div>
          </div>
        </div>

        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 px-2">What we collect</h3>
        
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="bg-white p-4 rounded-2xl flex items-center gap-3 shadow-sm border border-gray-100">
            <div className="bg-blue-50 p-2 rounded-lg text-[#00447C]"><FileCheck className="w-5 h-5"/></div>
            <span className="font-semibold text-[#00447C] text-sm">Health Info</span>
          </div>
          <div className="bg-white p-4 rounded-2xl flex items-center gap-3 shadow-sm border border-gray-100">
            <div className="bg-blue-50 p-2 rounded-lg text-[#00447C]"><FileCheck className="w-5 h-5"/></div>
            <span className="font-semibold text-[#00447C] text-sm">Medicines</span>
          </div>
          <div className="bg-white p-4 rounded-2xl flex items-center gap-3 shadow-sm border border-gray-100">
            <div className="bg-blue-50 p-2 rounded-lg text-[#00447C]"><FileCheck className="w-5 h-5"/></div>
            <span className="font-semibold text-[#00447C] text-sm">Allergies</span>
          </div>
          <div className="bg-white p-4 rounded-2xl flex items-center gap-3 shadow-sm border border-gray-100">
            <div className="bg-blue-50 p-2 rounded-lg text-[#00447C]"><FileCheck className="w-5 h-5"/></div>
            <span className="font-semibold text-[#00447C] text-sm">Reports & Symptoms</span>
          </div>
        </div>

        <div className="bg-[#00447C] text-white rounded-2xl p-5 mb-6">
          <h4 className="font-bold mb-2 flex items-center gap-2">
            <span className="bg-white/20 w-6 h-6 rounded-full flex items-center justify-center text-xs">?</span> 
            Why do we need this?
          </h4>
          <p className="text-sm text-blue-100 leading-relaxed">
            To help your doctor understand your health history better.
          </p>
        </div>

        <div 
          className="flex items-start gap-4 p-2 cursor-pointer" 
          onClick={() => setAgreed(!agreed)}
        >
          <div className="mt-1 text-[#008891]">
            {agreed ? <CheckSquare className="w-6 h-6" /> : <Square className="w-6 h-6" />}
          </div>
          <p className="text-sm text-gray-700 font-medium">
            I understand and agree to share my information.
          </p>
        </div>
      </div>
      
      <div className="p-6 bg-white border-t border-gray-100 flex flex-col gap-4">
        <button 
          disabled={!agreed}
          onClick={() => navigate('/department')}
          className={`w-full py-4 rounded-2xl font-bold text-lg transition-all ${
            agreed 
            ? 'bg-[#008891] text-white shadow-lg active:scale-95' 
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
        >
          Give consent & continue →
        </button>
        <button onClick={() => navigate(-1)} className="text-gray-400 text-sm font-semibold">
          I don't want to continue
        </button>
      </div>
    </div>
  )
}
