import { useNavigate } from 'react-router-dom'
import { useIntakeStore } from '../store/useIntakeStore'
import { User, Stethoscope } from 'lucide-react'

export function RoleSelection() {
  const navigate = useNavigate()
  const setRole = useIntakeStore(state => state.setRole)

  const handleSelect = (role: 'patient' | 'doctor') => {
    setRole(role)
    if (role === 'patient') {
      navigate('/identity')
    } else {
      navigate('/doctor/login')
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <div className="p-8 pt-16 flex-1 flex flex-col justify-center">
        <h1 className="text-2xl font-bold text-[#00447C] text-center mb-2">Welcome to MediKiosk</h1>
        <p className="text-gray-500 text-center mb-10">Select an option below to continue to your tailored experience.</p>

        <button 
          onClick={() => handleSelect('patient')}
          className="bg-white rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] mb-4 text-left border border-blue-50 transition-transform active:scale-95"
        >
          <div className="bg-blue-50 w-12 h-12 rounded-full flex items-center justify-center mb-4">
            <User className="w-6 h-6 text-[#008891]" />
          </div>
          <h2 className="text-xl font-bold text-[#00447C] mb-2">Patient</h2>
          <p className="text-gray-500 text-sm mb-4">Tell us about your health before meeting the doctor.</p>
          <div className="text-[#008891] font-semibold text-sm flex items-center">
            START MY HEALTH INTAKE →
          </div>
        </button>

        <button 
          onClick={() => handleSelect('doctor')}
          className="bg-[#00447C] rounded-3xl p-6 shadow-lg text-left text-white transition-transform active:scale-95"
        >
          <div className="bg-white/10 w-12 h-12 rounded-full flex items-center justify-center mb-4">
            <Stethoscope className="w-6 h-6 text-white" />
          </div>
          <h2 className="text-xl font-bold mb-2">Doctor / Staff</h2>
          <p className="text-blue-100 text-sm mb-4">Review patients and clinical dashboards.</p>
          <div className="text-white font-semibold text-sm flex items-center opacity-90">
            OPEN CLINICAL DASHBOARD →
          </div>
        </button>
      </div>

      <div className="p-6 text-center text-gray-500 text-sm flex justify-center items-center gap-2">
        <span>🌐 English</span>
      </div>
    </div>
  )
}
