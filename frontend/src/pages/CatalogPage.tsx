import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { S } from '../strings/en';

export function CatalogPage() {
  const cat = useData(api.catalog, 'catalog');
  const [params, setParams] = useSearchParams();
  useScreenContext({ variable: S.catalog.title }, []);
  if (cat.error) return <ErrorState error={cat.error} />;
  if (!cat.data) return <Loading />;
  const topic = params.get('topic') ?? '';
  const place = params.get('place') ?? '';
  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };
  const rows = cat.data.variables
    .filter((v) => !topic || v.topic === topic)
    .filter((v) => !place || v.anywhere || v.place_types.includes(place));
  const ready = rows.filter((v) => v.status === 'ready');
  const next = rows.filter((v) => v.status !== 'ready');
  const topicLabel = Object.fromEntries(cat.data.topics.map((t) => [t.id, t.label]));

  const chips = (key: string, value: string, options: { id: string; label: string }[]) => (
    <div className="chips">
      <button type="button" className={`chip${!value ? ' is-active' : ''}`} aria-pressed={!value} onClick={() => set(key, '')}>{S.catalog.all}</button>
      {options.map((o) => (
        <button key={o.id} type="button" className={`chip${value === o.id ? ' is-active' : ''}`} aria-pressed={value === o.id} onClick={() => set(key, o.id)}>{o.label}</button>
      ))}
    </div>
  );

  return (
    <div className="page">
      <header className="page__header">
        <h1>{S.catalog.title}</h1>
        <p className="lead">{S.catalog.intro}</p>
      </header>
      <div className="filters" role="group" aria-label="Filters">
        <div className="filters__row"><span className="filters__label">{S.catalog.topic}</span>{chips('topic', topic, cat.data.topics)}</div>
        <div className="filters__row"><span className="filters__label">{S.catalog.place}</span>{chips('place', place, cat.data.place_types)}</div>
      </div>

      <section className="catalog__block">
        <header className="catalog__head">
          <h2>{S.catalog.readyTitle}<span className="catalog__count">{ready.length}</span></h2>
          <p>{S.catalog.readyLead}</p>
        </header>
        {ready.length === 0 && <p className="muted">{S.catalog.none}</p>}
        <ul className="ready">
          {ready.map((v) => (
            <li key={v.id} className="ready__item">
              <p className="ready__topic">{topicLabel[v.topic] ?? v.topic}</p>
              <h3 className="ready__name">{v.name}</h3>
              <p className="ready__def">{v.definition}</p>
              <p className="ready__why"><span className="muted">{S.catalog.whyTrends}:</span> {v.why_it_trends}</p>
              <p className="ready__src">{v.source_short} · {v.period.split(' (')[0]}</p>
              {v.app_variable_id && <Link className="ready__go" to={`/?var=${v.app_variable_id}&case=none`}>{S.catalog.explore}</Link>}
            </li>
          ))}
        </ul>
      </section>

      {next.length > 0 && (
        <section className="catalog__block catalog__block--next">
          <header className="catalog__head">
            <h2>{S.catalog.nextTitle}<span className="catalog__count">{next.length}</span></h2>
            <p>{S.catalog.nextLead}</p>
          </header>
          <table className="catalog-next">
            <thead><tr><th scope="col">Variable</th><th scope="col">{S.catalog.whyTrends}</th><th scope="col">Source</th></tr></thead>
            <tbody>
              {next.map((v) => (
                <tr key={v.id}>
                  <td><span className="catalog-next__name">{v.name}</span><span className="catalog-next__def">{v.definition}</span></td>
                  <td>{v.why_it_trends}</td>
                  <td className="catalog-next__src">{v.source_short}<br />{v.period}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
