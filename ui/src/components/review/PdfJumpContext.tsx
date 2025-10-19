import React, { createContext, useContext } from 'react'

interface PdfJumpContextType {
  onJumpToPdf?: (fieldPath: string) => void
  currentPage?: number
}

const PdfJumpContext = createContext<PdfJumpContextType>({})

export function PdfJumpProvider({
  children,
  onJumpToPdf,
  currentPage
}: {
  children: React.ReactNode
  onJumpToPdf?: (fieldPath: string) => void
  currentPage?: number
}) {
  return (
    <PdfJumpContext.Provider value={{ onJumpToPdf, currentPage }}>
      {children}
    </PdfJumpContext.Provider>
  )
}

export function usePdfJump() {
  return useContext(PdfJumpContext)
}