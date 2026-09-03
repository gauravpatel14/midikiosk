import { useNavigate } from 'react-router-dom'
import { useIntakeStore } from '../store/useIntakeStore'
import { ArrowLeft, Volume2 } from 'lucide-react'

const languages = [
  { id: 'hi', name: 'हिन्दी', native: 'Hindi' },
  { id: 'en', name: 'English', native: 'English' },
  { id: 'mr', name: 'मराठी', native: 'Marathi' },
  { id: 'ta', name: 'தமிழ்', native: 'Tamil' },
  { id: 'bn', name: 'বাংলা', native: 'Bengali' },
  { id: 'te', name: 'తెలుగు', native: 'Telugu' },
  { id: 'gu', name: 'ગુજરાતી', native: 'Gujarati' },
  { id: 'kn', name: 'ಕನ್ನಡ', native: 'Kannada' },
  { id: 'ml', name: 'മലയാളം', native: 'Malayalam' },
  { id: 'pa', name: 'ਪੰਜਾਬੀ', native: 'Punjabi' },
]

export function LanguageSelection() {
  const navigate = useNavigate()
  const { language, setLanguage } = useIntakeStore()

  const handleSelect = (lang: string) => {
    setLanguage(lang)
    navigate('/welcome')
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
        <div className="flex justify-end mb-4">
          <button className="bg-blue-50 text-[#008891] p-2 rounded-full shadow-sm flex items-center gap-2 px-4 font-semibold text-sm">
            <Volume2 className="w-4 h-4" /> Listen
          </button>
        </div>
        
        <h2 className="text-2xl font-bold text-[#00447C] text-center mb-2">Choose your language</h2>
        <p className="text-gray-500 text-center text-sm mb-8 px-4">
          अपनी भाषा चुनें • अपनी भाषा चुनें • Select
        </p>

        <div className="grid grid-cols-2 gap-4">
          {languages.map((lang) => (
            <button
              key={lang.id}
              onClick={() => handleSelect(lang.name)}
              className={`p-4 rounded-2xl flex flex-col items-center justify-center gap-1 shadow-sm transition-all active:scale-95 border ${
                language === lang.name 
                  ? 'bg-[#00447C] text-white border-[#00447C]' 
                  : 'bg-white text-gray-700 border-gray-100'
              }`}
            >
              <span className={`text-xl font-bold ${language === lang.name ? 'text-white' : 'text-[#00447C]'}`}>{lang.name}</span>
              <span className={`text-xs ${language === lang.name ? 'text-blue-100' : 'text-gray-500'}`}>{lang.native}</span>
            </button>
          ))}
        </div>
        
        <div className="mt-8 text-center text-[#008891] font-semibold">
          + More languages
        </div>
      </div>
      
      <div className="p-6 bg-[#00447C] text-white text-center font-bold">
        |||||||| ||||||| 🔊
      </div>
    </div>
  )
}
