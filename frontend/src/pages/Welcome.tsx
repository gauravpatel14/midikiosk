import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Mic, FileText, CheckCircle2, Volume2 } from 'lucide-react'

export function Welcome() {
  const navigate = useNavigate()

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

      <div className="p-8 flex-1 flex flex-col items-center pt-8">
        <div className="w-20 h-20 bg-[#00447C] rounded-full flex items-center justify-center mb-6 shadow-lg text-white">
          <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        
        <h2 className="text-2xl font-bold text-[#00447C] text-center mb-3">Welcome</h2>
        <p className="text-gray-500 text-center text-sm mb-10 px-2 leading-relaxed">
          Let's prepare your health information before you meet your doctor.
        </p>

        <div className="w-full space-y-4 mb-10">
          <div className="bg-white p-5 rounded-2xl flex items-start gap-4 shadow-sm border border-gray-100">
            <div className="bg-[#E5F3F4] p-3 rounded-full text-[#008891] mt-1">
              <Mic className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-[#00447C] mb-1">Speak or Tap</h3>
              <p className="text-sm text-gray-500">Use your voice or touch to answer.</p>
            </div>
          </div>
          
          <div className="bg-white p-5 rounded-2xl flex items-start gap-4 shadow-sm border border-gray-100">
            <div className="bg-[#E5F3F4] p-3 rounded-full text-[#008891] mt-1">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-[#00447C] mb-1">Scan Reports</h3>
              <p className="text-sm text-gray-500">Prescriptions and medical papers.</p>
            </div>
          </div>
          
          <div className="bg-white p-5 rounded-2xl flex items-start gap-4 shadow-sm border border-gray-100">
            <div className="bg-[#E5F3F4] p-3 rounded-full text-[#008891] mt-1">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-[#00447C] mb-1">Ready for Doctor</h3>
              <p className="text-sm text-gray-500">History sent directly to clinic.</p>
            </div>
          </div>
        </div>

        <button 
          onClick={() => navigate('/consent')}
          className="bg-[#00447C] w-full rounded-2xl py-4 shadow-lg text-white font-bold text-lg active:scale-95 transition-transform"
        >
          Start →
        </button>
      </div>
      
      <div className="p-6 text-center text-xs text-gray-400 relative">
        <button className="absolute right-6 bottom-6 bg-[#008891] text-white p-4 rounded-full shadow-lg">
          <Volume2 className="w-6 h-6" />
        </button>
        Your health information is private and <br/>secure with your consent.
      </div>
    </div>
  )
}
