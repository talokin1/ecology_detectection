# Visual and UI Presentation Vision

## 1. Map Interface and Interactive Elements
The main website screen will feature an interactive Earth map. We will use a clean, color-blind-safe diverging palette to ensure accessibility:
- **Warm colors (Red/Orange):** to visually highlight positive changes on the map.
- **Cool colors (Blue):** to highlight negative changes.
- **Stippling pattern (dots):** used as a visual overlay on the map regions to indicate statistical significance without cluttering the screen.
- **Timeline Slider:** A UI control at the bottom to let users "play" the climate data over time.

## 2. Typography and Educational Formula Display (LaTeX UI)
Since this is a scientific application, the UI must balance readability with academic rigor. 
- We will use a modern, clean Sans-Serif font for general UI copy.
- When a user clicks on a region, a sidebar will slide out. Instead of plain text, the UI will display the formulas using elegant LaTeX rendering.
For example, the interface will present the trend magnitude formula like this:
$$ m = median \left( \frac{x_j - x_i}{j - i} \right) \text{ for } i < j $$

## 3. Verdict Card Design and Color Coding
The backend results will be displayed in a clean "Verdict Card" UI component. 
- The card will use color-coded badges to communicate results instantly: **Bright Green** for "Strong Evidence", **Yellow** for "Moderate", and **Grey** for "Inconclusive".
- Any complex mathematical text, such as $$ Var^*(S) = \eta \cdot Var(S) $$, will be hidden by default inside a dropdown "Geek Details" menu.

## 4. Narrative Flow and UI Copy
As an educational tool, the UI copy will follow a "plain language" approach. We will translate complex Earth science terminology into engaging, easy-to-understand storytelling. 

## 5. User Flow (Step-by-Step Experience)
To ensure a smooth user experience, the interface will follow this exact sequence:
1. **Onboarding (Wizard):** Upon entering the site, a short welcome popup explains how to read the map.
2. **Exploration:** The user views the global map and uses the timeline slider.
3. **Interaction:** The user clicks on a specific stippled region.
4. **Reveal:** The sidebar slides out, displaying the Verdict Card first, followed by the LaTeX math formulas for those who want to learn more.

## 6. Demo Video and Presentation Visuals
The 30-second demo video and the 7-slide pitch deck will utilize the same color-blind-safe palette, typography, and LaTeX highlight style to create a unified, professional brand for our team.
