import { create } from 'zustand'

interface IntakeState {
  role: 'patient' | 'doctor' | null
  abhaId: string | null
  language: string
  department: string | null
  symptoms: string[]
  setRole: (role: 'patient' | 'doctor') => void
  setAbhaId: (id: string) => void
  setLanguage: (lang: string) => void
  setDepartment: (dept: string) => void
  toggleSymptom: (symptom: string) => void
}

export const useIntakeStore = create<IntakeState>((set) => ({
  role: null,
  abhaId: null,
  language: 'English',
  department: null,
  symptoms: [],
  setRole: (role) => set({ role }),
  setAbhaId: (abhaId) => set({ abhaId }),
  setLanguage: (language) => set({ language }),
  setDepartment: (department) => set({ department }),
  toggleSymptom: (symptom) => set((state) => ({
    symptoms: state.symptoms.includes(symptom)
      ? state.symptoms.filter((s) => s !== symptom)
      : [...state.symptoms, symptom],
  })),
}))
