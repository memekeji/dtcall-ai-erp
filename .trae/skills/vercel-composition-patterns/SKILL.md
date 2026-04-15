---
name: "vercel-composition-patterns"
description: "React composition patterns that scale. Use when refactoring components with boolean prop proliferation, building flexible component libraries, or designing reusable APIs. Includes React 19 API changes."
---

# React Composition Patterns

Composition patterns for building flexible, maintainable React components. Avoid boolean prop proliferation by using compound components, lifting state, and composing internals.

## When to Apply

Reference these guidelines when:
- Refactoring components with many boolean props
- Building reusable component libraries
- Designing flexible component APIs
- Reviewing component architecture
- Working with compound components or context providers

## Rule Categories

### 1. Component Architecture (HIGH)

- `architecture-avoid-boolean-props` - Don't add boolean props to customize behavior; use composition
- `architecture-compound-components` - Structure complex components with shared context

### 2. State Management (MEDIUM)

- `state-decouple-implementation` - Provider is the only place that knows how state is managed
- `state-context-interface` - Define generic interface with state, actions, meta for dependency injection
- `state-lift-state` - Move state into provider components for sibling access

### 3. Implementation Patterns (MEDIUM)

- `patterns-explicit-variants` - Create explicit variant components instead of boolean modes
- `patterns-children-over-render-props` - Use children for composition instead of renderX props

### 4. React 19 APIs (MEDIUM)

> **⚠️ React 19+ only.** Skip this section if using React 18 or earlier.

- `react19-no-forwardref` - Don't use `forwardRef`; use `use()` instead of `useContext()`

## Key Patterns

### Avoid Boolean Props

**Bad:**
```tsx
<Button variant="primary" size="lg" disabled loading />
```

**Good - Compound Components:**
```tsx
<Button>
  <Button.Primary>Submit</Button.Primary>
  <Button.Loading>Loading...</Button.Loading>
</Button>
```

### Use Compound Components

```tsx
// Context-based compound components
const TabsContext = createContext({});

function Tabs({ children, defaultValue }) {
  const [active, setActive] = useState(defaultValue);
  return (
    <TabsContext.Provider value={{ active, setActive }}>
      {children}
    </TabsContext.Provider>
  );
}

function Tab({ value, children }) {
  const { active } = useContext(TabsContext);
  return active === value ? children : null;
}

Tabs.Tab = Tab;
```

### State Lifting

Move state into provider for sibling access:

```tsx
function FormProvider({ children }) {
  const [data, setData] = useState({});
  const [errors, setErrors] = useState({});
  
  return (
    <FormContext.Provider value={{ data, setData, errors, setErrors }}>
      {children}
    </FormContext.Provider>
  );
}

// Siblings can now share state without prop drilling
function FormFields() {
  const { data, setData } = useFormContext();
  // ...
}
```
