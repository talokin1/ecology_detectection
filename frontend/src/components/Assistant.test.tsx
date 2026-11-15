import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../lib/plotly', () => ({
  loadPlotly: () => Promise.resolve({ react: () => Promise.resolve(), purge: () => {} }),
  themeColors: () => ({ bg: '', text: '', text2: '', text3: '', line: '', lineStrong: '', ink: '', band: '' }),
  FONT: 'Inter',
}));

const reply = {
  answer: 'Ukraine warmed about +0.54 °C per decade.',
  suggestions: [{ variable_id: 'soil', region_id: 'south_ukraine', variable_name: 'Soil wetness', region_name: 'South Ukraine',
    why: 'Farm soils.', verdict: 'Evidence: drying', href: '#/region/south_ukraine?var=soil' }],
  looked_up: [{ tool: 'rank_regions', label: 'Ranking of places: Soil wetness, drier', href: null },
    { tool: 'get_analysis', label: 'Result: Air temperature · France', href: '#/region/c_fra?var=t2m' }],
  web_sources: [{ title: 'metoffice.gov.uk', uri: 'https://vertexaisearch.cloud.google.com/grounding-api-redirect/x', domain: 'metoffice.gov.uk' }],
  search_suggestions_html: '<div>2010 heatwave</div>',
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
  sessionStorage.clear();
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
    expect(screen.getByText('Ranking of places: Soil wetness, drier')).toBeTruthy();
    const web = screen.getByRole('link', { name: 'metoffice.gov.uk' });
    expect(web.getAttribute('href')).toBe('https://vertexaisearch.cloud.google.com/grounding-api-redirect/x');
    expect(web.getAttribute('target')).toBe('_blank');
    const frame = screen.getByTitle('Google Search suggestions for this answer');
    expect(frame.getAttribute('sandbox')).toBe('allow-popups allow-popups-to-escape-sandbox');
    expect(frame.getAttribute('srcdoc')).toContain('<div>2010 heatwave</div>');
    expect(screen.getByRole('link', { name: 'Result: Air temperature · France' }).getAttribute('href')).toBe('/region/c_fra?var=t2m');
    expect(screen.getByRole('link', { name: /Soil wetness · South Ukraine/ }).getAttribute('href')).toBe('/region/south_ukraine?var=soil');
  });

  it('shows the service error without breaking', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Too many questions right now.' }) }));
    const { Assistant } = await load();
    render(<MemoryRouter><Assistant context={null} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /ask the assistant/i }));
    fireEvent.click(screen.getByRole('button', { name: 'What does “no clear trend yet” mean?' }));
    await waitFor(() => expect(screen.getByText('Too many questions right now.')).toBeTruthy());
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it('renders Markdown answers, a chart from server data, and keeps the chat after a reload', async () => {
    const answer = '**Yes, it is warming.**\n\n| Place | Trend |\n|---|---|\n| Ukraine | +0.54 |\n\n- see [Ukraine](#/region/ukraine?var=t2m)';
    const chart = { kind: 'rates', title: 'Air temperature: trend per decade with 95% range', units: '°C per decade',
      source: 'NASA POWER (MERRA-2)', palette: 'RdBu',
      bars: [{ label: 'Ukraine', region_id: 'ukraine', value: 0.54, low: 0.38, high: 0.7, level: 'strong', level_word: 'Strong evidence' },
        { label: 'France', region_id: 'c_fra', value: 0.39, low: 0.28, high: 0.51, level: 'strong', level_word: 'Strong evidence' }] };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...reply, answer, chart, looked_up: [], web_sources: [] }) }));
    const { Assistant } = await load();
    const { unmount } = render(<MemoryRouter><Assistant context={null} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /ask the assistant/i }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Is Ukraine warming?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await screen.findByText('Yes, it is warming.');
    expect(screen.getByText('Yes, it is warming.').tagName).toBe('STRONG');
    expect(screen.getByRole('table')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Ukraine' }).getAttribute('href')).toBe('/region/ukraine?var=t2m');
    expect(await screen.findByText('Air temperature: trend per decade with 95% range')).toBeTruthy();
    unmount();
    render(<MemoryRouter><Assistant context={null} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /ask the assistant/i }));
    expect(screen.getByText('Yes, it is warming.')).toBeTruthy(); // restored from sessionStorage
    fireEvent.click(screen.getByRole('button', { name: 'New chat' }));
    expect(screen.queryByText('Yes, it is warming.')).toBeNull();
  });
});
