import React from 'react';

interface Props {
  title: string;
  description?: string;
  actionText?: string;
  onAction?: () => void;
  compact?: boolean;
}

export function EmptyState({ title, description, actionText, onAction, compact = false }: Props) {
  if (compact) {
    return (
      <div className="flex flex-col items-center justify-center py-6 px-4">
        <div className="w-12 h-12 mb-3 text-gray-400">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="m9 9 3 3 3-3" />
          </svg>
        </div>
        <h3 className="text-base font-medium text-gray-900 mb-1">{title}</h3>
        {description && (
          <p className="text-sm text-gray-500 text-center max-w-sm">{description}</p>
        )}
        {actionText && onAction && (
          <button
            onClick={onAction}
            className="mt-4 bg-blue-600 text-white py-1.5 px-3 text-sm rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {actionText}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4">
      <div className="w-16 h-16 mb-4 text-gray-400">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="m9 9 3 3 3-3" />
        </svg>
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>
      {description && (
        <p className="text-gray-500 text-center max-w-md mb-6">{description}</p>
      )}
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {actionText}
        </button>
      )}
    </div>
  );
}