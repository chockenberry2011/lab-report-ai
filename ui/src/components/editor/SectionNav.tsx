import React, { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/utils'

interface SectionNavSection {
  key: string
  title: string
  dirty: boolean
}

interface SectionNavProps {
  sections: SectionNavSection[]
  onSelect?: (key: string) => void
}

export function SectionNav({ sections, onSelect }: SectionNavProps) {
  const [activeSection, setActiveSection] = useState<string>('')

  // Track which section is currently in view
  useEffect(() => {
    const handleScroll = () => {
      const sectionElements = sections.map(section => ({
        key: section.key,
        element: document.getElementById(`section-${section.key}`)
      })).filter(item => item.element)

      // Find the section that's currently most visible
      const scrollPosition = window.scrollY + 100 // Offset for header/nav
      let currentSection = ''

      for (const { key, element } of sectionElements) {
        if (element && element.offsetTop <= scrollPosition) {
          currentSection = key
        }
      }

      setActiveSection(currentSection)
    }

    window.addEventListener('scroll', handleScroll)
    handleScroll() // Initial check

    return () => window.removeEventListener('scroll', handleScroll)
  }, [sections])

  const scrollToSection = (sectionKey: string) => {
    const element = document.getElementById(`section-${sectionKey}`)
    if (element) {
      const headerOffset = 80 // Account for sticky header
      const elementPosition = element.offsetTop - headerOffset
      window.scrollTo({
        top: elementPosition,
        behavior: 'smooth'
      })
    }
    if (onSelect) onSelect(sectionKey)
  }

  return (
    <nav className="sticky top-20 space-y-1">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Sections
      </div>

      {sections.map((section) => (
        <button
          key={section.key}
          onClick={() => scrollToSection(section.key)}
          className={cn(
            'w-full text-left px-3 py-2 text-sm rounded-md transition-colors duration-200 flex items-center justify-between group',
            activeSection === section.key
              ? 'bg-blue-100 text-blue-700 font-medium'
              : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
          )}
        >
          <span className="truncate">{section.title}</span>
          {section.dirty && (
            <div
              className="w-2 h-2 bg-amber-400 rounded-full flex-shrink-0"
              title="Unsaved changes"
            />
          )}
        </button>
      ))}
    </nav>
  )
}

interface MobileSectionNavProps {
  sections: SectionNavSection[]
}

export function MobileSectionNav({ sections }: MobileSectionNavProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<string>('')

  // Track active section (same logic as desktop)
  useEffect(() => {
    const handleScroll = () => {
      const sectionElements = sections.map(section => ({
        key: section.key,
        element: document.getElementById(`section-${section.key}`)
      })).filter(item => item.element)

      const scrollPosition = window.scrollY + 100
      let currentSection = ''

      for (const { key, element } of sectionElements) {
        if (element && element.offsetTop <= scrollPosition) {
          currentSection = key
        }
      }

      setActiveSection(currentSection)
    }

    window.addEventListener('scroll', handleScroll)
    handleScroll()

    return () => window.removeEventListener('scroll', handleScroll)
  }, [sections])

  const scrollToSection = (sectionKey: string) => {
    const element = document.getElementById(`section-${sectionKey}`)
    if (element) {
      const headerOffset = 80
      const elementPosition = element.offsetTop - headerOffset
      window.scrollTo({
        top: elementPosition,
        behavior: 'smooth'
      })
    }
    setIsOpen(false)
  }

  const activeTitle = sections.find(s => s.key === activeSection)?.title || 'Navigate to section'
  const hasDirtySection = sections.some(s => s.dirty)

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2 bg-white border border-gray-300 rounded-md shadow-sm text-sm text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <div className="flex items-center space-x-2">
          <span className="truncate">{activeTitle}</span>
          {hasDirtySection && (
            <div
              className="w-2 h-2 bg-amber-400 rounded-full flex-shrink-0"
              title="Unsaved changes in sections"
            />
          )}
        </div>
        {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-md shadow-lg z-20 max-h-64 overflow-y-auto">
            {sections.map((section) => (
              <button
                key={section.key}
                onClick={() => scrollToSection(section.key)}
                className={cn(
                  'w-full text-left px-4 py-2 text-sm hover:bg-gray-100 flex items-center justify-between first:rounded-t-md last:rounded-b-md',
                  activeSection === section.key && 'bg-blue-100 text-blue-700 font-medium'
                )}
              >
                <span className="truncate">{section.title}</span>
                {section.dirty && (
                  <div
                    className="w-2 h-2 bg-amber-400 rounded-full flex-shrink-0"
                    title="Unsaved changes"
                  />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
