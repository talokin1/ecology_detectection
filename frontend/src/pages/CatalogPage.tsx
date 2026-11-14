import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import { ErrorState, Loading, useScreenContext } from '../components/Shell';
import { S } from '../strings/en';

export function CatalogPage() {
  const cat = useData(api.catalog, 'catalog');
  const [params, setParams] = useSearchParams();
  useScreenContext({ variable: 'All variables' }, []);
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
    .filter((v) => !place || v.anywhere || v.place_types.includes(place))
    .sort((x, y) => Number(y.status === 'ready') - Number(x.status === 'ready'));
  const topicLabel = Object.fromEntries(cat.data.topics.map((t) => [t.id, t.label]));

  return (
    <div className="page">
      <header className="page__header">
        <h1>{S.catalog.title}</h1>
        <p className="lead">{S.catalog.intro}</p>
      </header>
      <div className="filters" role="group" aria-label="Filters">
        <div className="filters__row">
          <span className="filters__label">{S.catalog.topic}</span>
          <div className="chips">
            <button type="button" className={`chip${!topic ? ' is-active' : ''}`} aria-pressed={!topic} onClick={() => set('topic', '')}>{S.catalog.all}</button>
            {cat.data.topics.map((t) => (
              <button key={t.id} type="button" className={`chip${topic === t.id ? ' is-active' : ''}`} aria-pressed={topic === t.id} onClick={() => set('topic', t.id)}>{t.label}</button>
            ))}
          </div>
        </div>
        <div className="filters__row">
          <span className="filters__label">{S.catalog.place}</span>
          <div className="chips">
            <button type="button" className={`chip${!place ? ' is-active' : ''}`} aria-pressed={!place} onClick={() => set('place', '')}>{S.catalog.all}</button>
            {cat.data.place_types.map((p) => (
              <button key={p.id} type="button" className={`chip${place === p.id ? ' is-active' : ''}`} aria-pressed={place === p.id} onClick={() => set('place', p.id)}>{p.label}</button>
            ))}
          </div>
        </div>
      </div>
      <p className="muted catalog__count">{S.catalog.count(rows.length)}</p>
      <table className="catalog">
        <thead>
          <tr>
            <th scope="col">Variable</th>
            <th scope="col">{S.catalog.whyTrends}</th>
            <th scope="col">Source</th>
            <th scope="col"><span className="visually-hidden">Status</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((v) => (
            <tr key={v.id} className={v.status === 'ready' ? 'is-ready' : ''}>
              <td>
                <div className="catalog__name">{v.name}</div>
                <div className="catalog__def">{v.definition}</div>
                <div className="catalog__topic">{topicLabel[v.topic] ?? v.topic}</div>
              </td>
              <td className="catalog__why">{v.why_it_trends}</td>
              <td className="catalog__src">
                <div>{v.source}</div>
                <div className="muted">{v.period}{v.resolution ? ` · ${v.resolution}` : ''}</div>
              </td>
              <td className="catalog__status">
                {v.status === 'ready' && v.app_variable_id ? (
                  <Link className="btn btn--primary" to={`/?var=${v.app_variable_id}&case=none`}>{S.catalog.ready} →</Link>
                ) : (
                  <span className="muted">{S.catalog.planned}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
