/** The four functional icons allowed by decision D6 (close, info, search, menu). Never decorative. */
type P = { size?: number };
const base = (size: number) => ({ width: size, height: size, viewBox: '0 0 16 16', fill: 'none', 'aria-hidden': true as const });

export const CloseIcon = ({ size = 16 }: P) => (
  <svg {...base(size)}><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
);
export const InfoIcon = ({ size = 16 }: P) => (
  <svg {...base(size)}><circle cx="8" cy="8" r="6.3" stroke="currentColor" strokeWidth="1.4" /><path d="M8 7.2v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /><circle cx="8" cy="4.9" r="0.95" fill="currentColor" /></svg>
);
export const SearchIcon = ({ size = 16 }: P) => (
  <svg {...base(size)}><circle cx="7" cy="7" r="4.6" stroke="currentColor" strokeWidth="1.6" /><path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
);
export const MenuIcon = ({ size = 16 }: P) => (
  <svg {...base(size)}><circle cx="3" cy="8" r="1.4" fill="currentColor" /><circle cx="8" cy="8" r="1.4" fill="currentColor" /><circle cx="13" cy="8" r="1.4" fill="currentColor" /></svg>
);
