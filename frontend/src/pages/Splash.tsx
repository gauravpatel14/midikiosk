import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity } from 'lucide-react'

export function Splash() {
  const navigate = useNavigate()

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate('/role')
    }, 2000)
    return () => clearTimeout(timer)
  }, [navigate])

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center bg-white">
      <div className="w-24 h-24 bg-blue-50 rounded-full flex items-center justify-center mb-8">
        <Activity className="w-12 h-12 text-[#008891]" />
      </div>
      <h1 className="text-3xl font-bold text-[#00447C] mb-2">MediKiosk</h1>
      <p className="text-gray-500 mb-12">Your health history, ready before the doctor.</p>
      
      <div className="flex items-center gap-3 text-[#008891] bg-blue-50 px-4 py-2 rounded-full">
        <div className="w-2 h-2 bg-[#008891] rounded-full animate-pulse" />
        <span className="text-sm font-medium">Starting MediKiosk ready...</span>
      </div>
      
      <div className="absolute bottom-8 text-xs text-gray-400 uppercase tracking-widest font-semibold">
        Designed for Ayushman Bharat<br/>ABDM Ready
      </div>
    </div>
  )
}
