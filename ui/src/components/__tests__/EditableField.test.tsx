/**
 * Unit tests for EditableField component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { EditableField } from '../EditableField';
import * as corrections from '../../lib/corrections';

// Mock the corrections module
jest.mock('../../lib/corrections');
const mockSaveCorrections = corrections.saveCorrections as jest.MockedFunction<typeof corrections.saveCorrections>;

describe('EditableField', () => {
  beforeEach(() => {
    mockSaveCorrections.mockClear();
    mockSaveCorrections.mockResolvedValue(true);
  });

  it('renders field with value and label', () => {
    render(
      <EditableField
        resultId="test-id"
        path="patient.first_name"
        label="Patient First Name"
        value="John"
      />
    );

    expect(screen.getByText('Patient First Name')).toBeInTheDocument();
    expect(screen.getByText('John')).toBeInTheDocument();
    expect(screen.getByText('Edit')).toBeInTheDocument();
  });

  it('renders placeholder when value is empty', () => {
    render(
      <EditableField
        resultId="test-id"
        path="patient.first_name"
        label="Patient First Name"
        value=""
        placeholder="Enter first name"
      />
    );

    expect(screen.getByText('Enter first name')).toBeInTheDocument();
  });

  it('enters edit mode when Edit button clicked', () => {
    render(
      <EditableField
        resultId="test-id"
        path="patient.first_name"
        label="Patient First Name"
        value="John"
      />
    );

    fireEvent.click(screen.getByText('Edit'));

    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByDisplayValue('John')).toBeInTheDocument();
    expect(screen.getByText('Save')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
    expect(screen.getByText('Unset')).toBeInTheDocument();
  });

  it('saves changes when Save button clicked', async () => {
    const mockOnChange = jest.fn();
    
    render(
      <EditableField
        resultId="test-id"
        path="patient.first_name"
        label="Patient First Name"
        value="John"
        onLocalChange={mockOnChange}
      />
    );

    // Enter edit mode
    fireEvent.click(screen.getByText('Edit'));
    
    // Change value
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Jane' } });
    
    // Save
    fireEvent.click(screen.getByText('Save'));

    // Verify API call
    await waitFor(() => {
      expect(mockSaveCorrections).toHaveBeenCalledWith('test-id', [
        { path: 'patient.first_name', value: 'Jane' }
      ]);
    });

    // Verify local change callback
    expect(mockOnChange).toHaveBeenCalledWith('Jane');
  });

  it('cancels changes when Cancel button clicked', () => {
    render(
      <EditableField
        resultId="test-id"
        path="patient.first_name"
        label="Patient First Name"
        value="John"
      />
    );

    // Enter edit mode
    fireEvent.click(screen.getByText('Edit'));
    
    // Change value
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Jane' } });
    
    // Cancel
    fireEvent.click(screen.getByText('Cancel'));

    // Should exit edit mode and not save
    expect(screen.getByText('John')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(mockSaveCorrections).not.toHaveBeenCalled();
  });

  it('unsets field when Unset button clicked', async () => {
    const mockOnChange = jest.fn();
    
    render(
      <EditableField
        resultId="test-id"
        path="patient.first_name"
        label="Patient First Name"
        value="John"
        onLocalChange={mockOnChange}
      />
    );

    // Enter edit mode
    fireEvent.click(screen.getByText('Edit'));
    
    // Unset
    fireEvent.click(screen.getByText('Unset'));

    // Verify API call
    await waitFor(() => {
      expect(mockSaveCorrections).toHaveBeenCalledWith('test-id', [
        { op: 'unset', path: 'patient.first_name' }
      ]);
    });

    // Verify local change callback
    expect(mockOnChange).toHaveBeenCalledWith(undefined);
  });

  it('shows error when save fails', async () => {
    mockSaveCorrections.mockRejectedValueOnce(new Error('Network error'));
    
    render(
      <EditableField
        resultId="test-id"
        path="patient.first_name"
        label="Patient First Name"
        value="John"
      />
    );

    // Enter edit mode and try to save
    fireEvent.click(screen.getByText('Edit'));
    fireEvent.click(screen.getByText('Save'));

    // Wait for error to appear
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('handles different input types', () => {
    render(
      <EditableField
        resultId="test-id"
        path="patient.dob"
        label="Date of Birth"
        value="1985-03-15"
        type="date"
      />
    );

    fireEvent.click(screen.getByText('Edit'));
    
    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('type', 'date');
  });

  it('disables buttons when saving', async () => {
    // Make save promise hang to test loading state
    mockSaveCorrections.mockImplementation(() => new Promise(() => {}));
    
    render(
      <EditableField
        resultId="test-id"
        path="patient.first_name"
        label="Patient First Name"
        value="John"
      />
    );

    fireEvent.click(screen.getByText('Edit'));
    fireEvent.click(screen.getByText('Save'));

    // Buttons should be disabled during save
    await waitFor(() => {
      expect(screen.getByText('Save')).toBeDisabled();
      expect(screen.getByText('Cancel')).toBeDisabled();
      expect(screen.getByText('Unset')).toBeDisabled();
    });
  });
});