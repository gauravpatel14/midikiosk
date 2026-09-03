import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, X, Maximize } from 'lucide-react'

export function Scanner() {
  const navigate = useNavigate()

  useEffect(() => {
    // Mock scanner delay
    const timer = setTimeout(() => {
      navigate('/language')
    }, 3000)
    return () => clearTimeout(timer)
  }, [navigate])

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="p-6 flex items-center justify-between border-b border-gray-100 bg-white">
        <div className="flex items-center">
          <button onClick={() => navigate(-1)} className="p-2 -ml-2 text-gray-500">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-xl font-bold text-[#00447C] ml-2">Patient Identity</h1>
        </div>
        <button onClick={() => navigate('/language')} className="p-2 text-gray-500">
          <X className="w-6 h-6" />
        </button>
      </header>

      <div className="p-8 flex-1 flex flex-col items-center pt-12">
        <h2 className="text-2xl font-bold text-[#00447C] text-center mb-2">Scan ABHA QR Code</h2>
        <p className="text-gray-500 text-center text-sm mb-10 px-4">
          Position the QR code inside the frame to link your health records.
        </p>

        <div className="relative w-64 h-64 bg-gray-900 rounded-3xl overflow-hidden mb-12 shadow-2xl flex items-center justify-center">
          {/* Mock Camera Feed */}
          <div className="absolute inset-0 opacity-50 bg-[url('https://images.unsplash.com/photo-1518770660439-4636190af475?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80')] bg-cover bg-center grayscale mix-blend-overlay"></div>
          
          <div className="absolute inset-4 border-2 border-[#008891] rounded-2xl">
            <div className="absolute -top-1 -left-1 w-6 h-6 border-t-4 border-l-4 border-white rounded-tl-xl"></div>
            <div className="absolute -top-1 -right-1 w-6 h-6 border-t-4 border-r-4 border-white rounded-tr-xl"></div>
            <div className="absolute -bottom-1 -left-1 w-6 h-6 border-b-4 border-l-4 border-white rounded-bl-xl"></div>
            <div className="absolute -bottom-1 -right-1 w-6 h-6 border-b-4 border-r-4 border-white rounded-br-xl"></div>
          </div>
          
          <div className="bg-white/20 backdrop-blur-md px-6 py-2 rounded-full text-white font-medium z-10 animate-pulse">
            Scanning...
          </div>
        </div>

        <div className="relative w-full mb-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-4 bg-[#F8FBFC] text-gray-400 font-medium">OR</span>
          </div>
        </div>

        <button 
          onClick={() => navigate('/language')}
          className="bg-white w-full rounded-2xl p-4 shadow-sm border border-gray-100 flex items-center justify-center gap-3 text-[#00447C] font-semibold active:scale-95 transition-transform"
        >
          <Maximize className="w-5 h-5" />
          <span>Enter ABHA Number Manually</span>
        </button>
      </div>
      
      <div className="p-6 bg-white border-t border-gray-100 flex gap-4">
        <button onClick={() => navigate(-1)} className="flex-1 py-4 text-gray-500 font-semibold border border-gray-200 rounded-2xl">Cancel</button>
        <button onClick={() => navigate('/language')} className="flex-1 py-4 bg-[#008891] text-white font-semibold rounded-2xl">Upload Image</button>
      </div>
    </div>
  )
}
