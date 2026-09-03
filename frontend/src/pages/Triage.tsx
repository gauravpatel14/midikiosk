import { useNavigate } from 'react-router-dom'
import { useIntakeStore } from '../store/useIntakeStore'
import { ArrowLeft, Mic, Activity, Thermometer, Wind, Zap, Skull, Headset, BatteryWarning, CalendarSync, Pill, MoreHorizontal } from 'lucide-react'

const symptomsList = [
  { id: 'pain', label: 'Pain', icon: Activity, color: 'text-red-500', bg: 'bg-red-50' },
  { id: 'fever', label: 'Fever', icon: Thermometer, color: 'text-orange-500', bg: 'bg-orange-50' },
  { id: 'breathing', label: 'Breathing Issue', icon: Wind, color: 'text-emerald-500', bg: 'bg-emerald-50' },
  { id: 'stomach', label: 'Stomach / Digestion', icon: Zap, color: 'text-blue-500', bg: 'bg-blue-50' },
  { id: 'skin', label: 'Skin Problem', icon: Skull, color: 'text-purple-500', bg: 'bg-purple-50' },
  { id: 'headache', label: 'Headache', icon: Headset, color: 'text-pink-500', bg: 'bg-pink-50' },
  { id: 'weakness', label: 'Weakness / Fatigue', icon: BatteryWarning, color: 'text-gray-500', bg: 'bg-gray-50' },
  { id: 'followup', label: 'Follow-up Visit', icon: CalendarSync, color: 'text-[#008891]', bg: 'bg-[#E5F3F4]' },
  { id: 'medicine', label: 'Medicine Review', icon: Pill, color: 'text-[#00447C]', bg: 'bg-blue-50' },
  { id: 'other', label: 'Other', icon: MoreHorizontal, color: 'text-gray-400', bg: 'bg-gray-100' },
]

export function Triage() {
  const navigate = useNavigate()
  const { symptoms, toggleSymptom } = useIntakeStore()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="p-6 flex items-center justify-between border-b border-gray-100 bg-white shadow-sm z-10 relative">
        <div className="flex items-center">
          <button onClick={() => navigate(-1)} className="p-2 -ml-2 text-gray-500">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-xl font-bold text-[#00447C] ml-2">Triage Assessment</h1>
        </div>
      </header>

      <div className="p-6 flex-1 overflow-y-auto">
        <h2 className="text-2xl font-bold text-[#00447C] text-center mb-2 mt-4">What brings you here today?</h2>
        <p className="text-gray-500 text-center text-sm mb-8 px-4">
          Select an option below or tap the microphone to describe your symptoms in your own words.
        </p>

        <div className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 mb-8 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 bg-[#00447C] rounded-full flex items-center justify-center text-white shadow-lg mb-4 cursor-pointer hover:bg-[#00335c] active:scale-95 transition-all">
            <Mic className="w-8 h-8" />
          </div>
          <h3 className="font-bold text-[#00447C] mb-2 text-lg">Speak Instead</h3>
          <p className="text-sm text-gray-500 bg-gray-50 p-3 rounded-xl italic">
            e.g. "I have severe chest pain since 2 hours"
          </p>
        </div>

        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200"></div>
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="px-4 bg-[#F8FBFC] text-gray-400 font-bold tracking-wider uppercase">OR SELECT CATEGORY</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-6">
          {symptomsList.map((item) => {
            const Icon = item.icon
            const isSelected = symptoms.includes(item.id)
            return (
              <button
                key={item.id}
                onClick={() => toggleSymptom(item.id)}
                className={`p-4 rounded-2xl flex flex-col items-center justify-center gap-3 transition-all active:scale-95 border-2 ${
                  isSelected 
                    ? 'border-[#008891] bg-white shadow-md' 
                    : 'border-transparent bg-white shadow-sm'
                }`}
              >
                <div className={`p-3 rounded-full ${isSelected ? 'bg-[#008891] text-white' : `${item.bg} ${item.color}`}`}>
                  <Icon className="w-6 h-6" />
                </div>
                <span className={`font-semibold text-sm text-center ${isSelected ? 'text-[#008891]' : 'text-gray-700'}`}>
                  {item.label}
                </span>
              </button>
            )
          })}
        </div>
      </div>
      
      {symptoms.length > 0 && (
        <div className="p-6 bg-white border-t border-gray-100 sticky bottom-0 z-10 animate-fade-in-up">
          <button 
            onClick={() => alert('Proceeding to next step...')}
            className="w-full bg-[#00447C] text-white py-4 rounded-2xl font-bold text-lg shadow-lg active:scale-95 transition-transform"
          >
            Continue with {symptoms.length} selected →
          </button>
        </div>
      )}
    </div>
  )
}
