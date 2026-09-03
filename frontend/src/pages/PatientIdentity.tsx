import { useNavigate } from 'react-router-dom'
import { QrCode, Keyboard, UserPlus, ArrowLeft } from 'lucide-react'

export function PatientIdentity() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="p-6 flex items-center border-b border-gray-100 bg-white">
        <button onClick={() => navigate(-1)} className="p-2 -ml-2 text-gray-500">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <h1 className="text-xl font-bold text-[#00447C] ml-2">Patient Identity</h1>
      </header>

      <div className="p-8 flex-1 flex flex-col justify-center">
        <h2 className="text-2xl font-bold text-[#00447C] text-center mb-2">Let's find your health record</h2>
        <p className="text-gray-500 text-center text-sm mb-8">Choose how you would like to securely access your Ayushman Bharat Health Account (ABHA).</p>

        <button 
          onClick={() => navigate('/scan')}
          className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 mb-4 flex flex-col items-center justify-center text-center transition-all active:scale-95"
        >
          <div className="mb-4 text-[#008891]">
            <QrCode className="w-16 h-16" strokeWidth={1} />
          </div>
          <h3 className="font-bold text-[#00447C] mb-1">Scan ABHA QR Code</h3>
          <p className="text-sm text-gray-500">Fastest way to check-in</p>
        </button>

        <button 
          onClick={() => navigate('/language')}
          className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 mb-6 flex items-center justify-between active:scale-95 transition-transform"
        >
          <div className="flex items-center gap-4">
            <div className="bg-gray-50 p-3 rounded-full">
              <Keyboard className="w-5 h-5 text-gray-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-[#00447C]">Enter ABHA Number</h3>
              <p className="text-xs text-gray-500">Type your 14-digit health ID</p>
            </div>
          </div>
          <span className="text-gray-300">›</span>
        </button>

        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-4 bg-[#F8FBFC] text-gray-400 font-medium">OR</span>
          </div>
        </div>

        <button 
          onClick={() => navigate('/language')}
          className="bg-[#E5F3F4] rounded-2xl p-4 flex items-center justify-center gap-3 text-[#008891] font-semibold active:scale-95 transition-transform"
        >
          <UserPlus className="w-5 h-5" />
          <span>Don't have an ABHA yet? Register as a new patient</span>
        </button>
        
        <div className="mt-8 text-center text-sm text-[#008891] font-medium underline underline-offset-4">
          Need help finding your ABHA?
        </div>
      </div>
    </div>
  )
}
