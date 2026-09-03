import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, QrCode } from 'lucide-react'

export function DoctorLogin() {
  const navigate = useNavigate()
  const [pin, setPin] = useState('')

  const handleKeyPress = (num: string) => {
    if (pin.length < 4) {
      const newPin = pin + num
      setPin(newPin)
      if (newPin.length === 4) {
        // Auto submit
        setTimeout(() => navigate('/doctor/dashboard'), 300)
      }
    }
  }

  const handleDelete = () => {
    setPin(pin.slice(0, -1))
  }

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="p-6 pb-2 flex items-center">
        <button onClick={() => navigate('/role')} className="text-gray-500">
          <ArrowLeft className="w-6 h-6" />
        </button>
        <span className="ml-2 font-semibold text-[#00447C]">Role Selection</span>
      </header>

      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <div className="w-16 h-16 bg-[#00447C] text-white rounded-2xl flex items-center justify-center text-3xl font-bold mb-4 shadow-lg">
          M
        </div>
        <h1 className="text-2xl font-bold text-[#00447C] mb-1">MediKiosk Staff</h1>
        <p className="text-gray-500 text-sm mb-12">All India Institute of Ayurveda</p>

        <p className="text-sm font-semibold text-[#00447C] mb-6">Enter Secret 4-Digit PIN</p>
        
        <div className="flex gap-4 mb-12">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={`w-4 h-4 rounded-full ${i < pin.length ? 'bg-[#008891]' : 'bg-gray-200'}`} />
          ))}
        </div>

        <div className="grid grid-cols-3 gap-6 w-full max-w-[280px]">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((num) => (
            <button 
              key={num}
              onClick={() => handleKeyPress(num.toString())}
              className="bg-white text-[#00447C] text-2xl font-semibold h-16 rounded-2xl shadow-sm border border-gray-100 active:scale-95 transition-transform"
            >
              {num}
            </button>
          ))}
          <button 
            className="text-gray-400 font-semibold active:scale-95 transition-transform"
            onClick={() => setPin('')}
          >
            Clear
          </button>
          <button 
            onClick={() => handleKeyPress('0')}
            className="bg-white text-[#00447C] text-2xl font-semibold h-16 rounded-2xl shadow-sm border border-gray-100 active:scale-95 transition-transform"
          >
            0
          </button>
          <button 
            className="text-gray-400 font-semibold active:scale-95 transition-transform"
            onClick={handleDelete}
          >
            Delete
          </button>
        </div>

        <button className="mt-12 bg-white px-6 py-3 rounded-full flex items-center gap-2 shadow-sm border border-gray-100 text-[#008891] font-semibold active:scale-95">
          <QrCode className="w-5 h-5" />
          Scan Staff ID Badge
        </button>
      </div>

      <div className="p-6 text-center text-xs text-[#008891] font-medium underline">
        Need Help? Contact Clinic Support
      </div>
    </div>
  )
}
