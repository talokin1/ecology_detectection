import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const reply = {
  answer: 'Ukraine warmed about +0.54 °C per decade.',
  suggestions: [{ variable_id: 'soil', region_id: 'south_ukraine', variable_name: 'Soil wetness', region_name: 'South Ukraine',
    why: 'Farm soils.', verdict: 'Evidence: drying', href: '#/region/south_ukraine?var=soil' }],
  unverified_numbers: ['7.7'],
  model: 'gemini-test',
  disclaimer: 'AI-generated',
};

async function load() {
  vi.resetModules();
  vi.stubEnv('VITE_ASSISTANT_URL', 'https://assistant.example/');
  return import('./Assistant');
}

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe('Assistant', () => {
  it('sends the on-screen ids and shows a labelled, grounded reply', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => reply });
    vi.stubGlobal('fetch', fetchMock);
    const { Assistant, assistantEnabled } = await load();
    expect(assistantEnabled).toBe(true);
    render(<MemoryRouter><Assistant context={{ variable: 'Air temperature', region: 'Ukraine', variableId: 't2m', regionId: 'ukraine' }} /></MemoryRouter>);

    fireEvent.click(screen.getByRole('button', { name: /ask the assistant/i }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What does this mean?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));

    await screen.findByText(reply.answer);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://assistant.example/v1/chat');
    expect(JSON.parse(init.body)).toMatchObject({ message: 'What does this mean?', region_id: 'ukraine', variable_id: 't2m', history: [] });
    expect(screen.getByText(/AI-generated · gemini-test/)).toBeTruthy();
    expect(screen.getByText(/Check these numbers: 7.7/)).toBeTruthy();
    expect(screen.getByRole('link', { name: /Soil wetness · South Ukraine/ }).getAttribute('href')).toBe('/region/south_ukraine?var=soil');
  });

  it('shows the service error without breaking', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Too many questions right now.' }) }));
    const { Assistant } = await load();
    render(<MemoryRouter><Assistant context={null} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /ask the assistant/i }));
    fireEvent.click(screen.getByRole('button', { name: 'What is a p-value?' }));
    await waitFor(() => expect(screen.getByText('Too many questions right now.')).toBeTruthy());
  });
});
