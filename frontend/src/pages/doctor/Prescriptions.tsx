
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, User, Search, Plus, Save } from 'lucide-react'

export function Prescriptions() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="bg-[#00447C] p-4 text-white flex justify-between items-center shadow-md z-10 sticky top-0">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="p-1 -ml-1">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <span className="font-semibold">Prescriptions</span>
        </div>
        <User className="w-8 h-8 bg-white/20 rounded-full p-1" />
      </header>

      <div className="p-4 flex-1 overflow-y-auto">
        <div className="text-xs font-semibold text-[#008891] mb-4 flex items-center gap-2">
          <span className="w-2 h-2 bg-[#008891] rounded-full"></span>
          Active Case: Patient A126 • 62y • Male • PID: 1982
        </div>

        <div className="relative mb-6">
          <Search className="w-5 h-5 absolute left-3 top-2.5 text-gray-400" />
          <input 
            type="text" 
            placeholder="Search medicine name or generic..." 
            className="w-full bg-white border border-gray-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#008891]/50 shadow-sm"
          />
        </div>

        <h3 className="font-bold text-[#00447C] mb-3">Active Prescriptions (2)</h3>
        
        <div className="space-y-3 mb-8">
          <div className="bg-white p-4 rounded-2xl shadow-sm border border-[#008891]/30 relative overflow-hidden">
            <div className="absolute top-0 right-0 bg-[#E5F3F4] text-[#008891] text-[10px] font-bold px-2 py-1 rounded-bl-lg">Active</div>
            <h4 className="font-bold text-[#00447C] mb-1">Tab. Paracetamol 500mg</h4>
            <p className="text-xs text-gray-500 mb-2">Dosage: 1 Tab • Frequency: TDS (3x/day) • Route: Oral</p>
            <p className="text-xs text-gray-600 bg-gray-50 p-2 rounded italic">
              Instructions: After meals, SOS for fever &gt; 100°F
            </p>
          </div>
          
          <div className="bg-white p-4 rounded-2xl shadow-sm border border-[#008891]/30 relative overflow-hidden">
            <div className="absolute top-0 right-0 bg-[#E5F3F4] text-[#008891] text-[10px] font-bold px-2 py-1 rounded-bl-lg">Active</div>
            <h4 className="font-bold text-[#00447C] mb-1">Syp. Gelusil MPS</h4>
            <p className="text-xs text-gray-500 mb-2">Dosage: 10 ml • Frequency: BD (2x/day) • Route: Oral</p>
            <p className="text-xs text-gray-600 bg-gray-50 p-2 rounded italic">
              Instructions: 15 mins before meals. For acidity.
            </p>
          </div>
        </div>

        <h3 className="font-bold text-[#00447C] mb-3">Add New Prescription</h3>
        
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-[#00447C] mb-6">
          <div className="mb-4">
            <label className="block text-xs font-bold text-gray-500 mb-1">Medicine Name *</label>
            <input type="text" value="Tab. Pantocid DSR" readOnly className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm text-[#00447C] font-semibold" />
          </div>
          
          <div className="flex gap-4 mb-4">
            <div className="flex-1">
              <label className="block text-xs font-bold text-gray-500 mb-1">Dosage *</label>
              <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                <button className="flex-1 bg-[#00447C] text-white py-1.5 text-xs font-bold">1 Tablet</button>
              </div>
            </div>
          </div>
          
          <div className="mb-4">
            <label className="block text-xs font-bold text-gray-500 mb-1">Frequency *</label>
            <div className="grid grid-cols-4 gap-2">
              <button className="bg-[#00447C] text-white py-2 rounded-lg text-xs font-bold">OD</button>
              <button className="bg-gray-50 text-gray-600 border border-gray-200 py-2 rounded-lg text-xs font-bold">BD</button>
              <button className="bg-gray-50 text-gray-600 border border-gray-200 py-2 rounded-lg text-xs font-bold">TDS</button>
              <button className="bg-gray-50 text-gray-600 border border-gray-200 py-2 rounded-lg text-xs font-bold">SOS</button>
            </div>
          </div>
          
          <div className="mb-4">
            <label className="block text-xs font-bold text-gray-500 mb-1">Duration *</label>
            <input type="text" value="5 Days" readOnly className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          
          <div className="mb-6">
            <label className="block text-xs font-bold text-gray-500 mb-1">Special Instructions</label>
            <textarea className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm h-16" defaultValue="Take in morning on empty stomach." />
          </div>
          
          <button className="w-full bg-[#E5F3F4] text-[#008891] border border-[#008891] py-3 rounded-xl font-bold text-sm active:scale-95 transition-transform flex items-center justify-center gap-2">
            <Plus className="w-4 h-4" /> ADD TO PRESCRIPTION
          </button>
        </div>
        
        <div className="bg-[#00447C]/5 rounded-2xl p-4 flex items-center justify-between border border-[#00447C]/10 mb-6">
          <span className="font-bold text-[#00447C] text-sm">Prescription Rx Summary</span>
          <span className="bg-[#00447C] text-white text-xs font-bold px-2 py-1 rounded-md">3 Meds Selected</span>
        </div>
        
        <button 
          className="w-full bg-[#00447C] text-white py-4 rounded-2xl font-bold text-lg active:scale-95 transition-transform flex items-center justify-center gap-2 mb-4 shadow-md"
        >
          <Save className="w-5 h-5" />
          PREVIEW & SIGN RX
        </button>
        
        <button className="w-full text-center py-2 text-gray-400 font-semibold text-sm">
          Save Draft
        </button>
      </div>
    </div>
  )
}
