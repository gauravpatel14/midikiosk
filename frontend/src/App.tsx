import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Splash } from './pages/Splash'
import { RoleSelection } from './pages/RoleSelection'
import { PatientIdentity } from './pages/PatientIdentity'
import { Scanner } from './pages/Scanner'
import { LanguageSelection } from './pages/LanguageSelection'
import { Welcome } from './pages/Welcome'
import { Consent } from './pages/Consent'
import { Department } from './pages/Department'
import { Triage } from './pages/Triage'

// Doctor Routes
import { DoctorLayout } from './layouts/DoctorLayout'
import { DoctorLogin } from './pages/doctor/DoctorLogin'
import { Dashboard } from './pages/doctor/Dashboard'
import { PatientQueue } from './pages/doctor/PatientQueue'
import { PatientDetail } from './pages/doctor/PatientDetail'
import { ClinicalNotes } from './pages/doctor/ClinicalNotes'
import { Prescriptions } from './pages/doctor/Prescriptions'
import { LabResults } from './pages/doctor/LabResults'
import { ShiftHandoff } from './pages/doctor/ShiftHandoff'
import { StaffSettings } from './pages/doctor/StaffSettings'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#F8FBFC] flex items-center justify-center">
        <div className="w-full max-w-md h-[100dvh] sm:h-[844px] bg-white shadow-2xl relative overflow-hidden sm:rounded-[40px] sm:border-8 border-gray-900">
          <Routes>
            {/* Patient Intake Routes */}
            <Route path="/" element={<Splash />} />
            <Route path="/role" element={<RoleSelection />} />
            <Route path="/identity" element={<PatientIdentity />} />
            <Route path="/scan" element={<Scanner />} />
            <Route path="/language" element={<LanguageSelection />} />
            <Route path="/welcome" element={<Welcome />} />
            <Route path="/consent" element={<Consent />} />
            <Route path="/department" element={<Department />} />
            <Route path="/triage" element={<Triage />} />

            {/* Doctor Routes */}
            <Route path="/doctor/login" element={<DoctorLogin />} />
            
            <Route path="/doctor" element={<DoctorLayout />}>
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="queue" element={<PatientQueue />} />
              <Route path="patient/:id" element={<PatientDetail />} />
              <Route path="notes/:id" element={<ClinicalNotes />} />
              <Route path="prescriptions" element={<Prescriptions />} />
              <Route path="labs" element={<LabResults />} />
              <Route path="handoff" element={<ShiftHandoff />} />
              <Route path="settings" element={<StaffSettings />} />
            </Route>
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}
