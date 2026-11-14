import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../data/load';
import { useData } from '../data/useData';
import { useScreenContext } from '../components/Shell';
import { S } from '../strings/en';

const A = S.about;

/** What the tool is, how to use it, data sources, credits and SI disclosure (plan B4). */
export function AboutPage() {
  const index = useData(api.index, 'index');
  const [params] = useSearchParams();
  useScreenContext({ variable: A.title }, []);
  useEffect(() => {
    const s = params.get('s');
    if (s) document.getElementById(s)?.scrollIntoView({ block: 'start' });
  }, [params, index.data]);

  return (
    <div className="page about">
      <header className="page__header">
        <h1>{A.title}</h1>
        <p className="about__tagline">{S.tagline}</p>
        <p className="lead">{A.lead}</p>
      </header>

      <section className="msec">
        <h2>{A.how}</h2>
        <ol className="about__steps">
          {A.howSteps.map((t, i) => <li key={i}>{t}</li>)}
        </ol>
        <p><Link className="btn btn--primary" to="/?tour=1">{S.shell.tour}</Link></p>
      </section>

      <section id="data" className="msec">
        <h2>{A.data}</h2>
        {index.data?.synthetic && <p className="callout">{A.syntheticNotice}</p>}
        <h3 className="h3">{A.sources}</h3>
        <ul className="bullets">
          {A.sourceList.map(([name, url, what]) => (
            <li key={name}><a href={url} target="_blank" rel="noreferrer">{name}</a>: {what}.</li>
          ))}
        </ul>
        <p className="help">{A.software}</p>
        <p><Link to="/methods">{S.case.dataMethods} →</Link></p>
      </section>

      <section id="si" className="msec">
        <h2>{A.si}</h2>
        <p>{A.siText}</p>
      </section>

      <section id="code" className="msec">
        <h2>{A.code}</h2>
        <p>{A.codeText} <a href={A.repo} target="_blank" rel="noreferrer">{A.repo.replace('https://', '')}</a></p>
        <p className="help">{A.noBranding}</p>
      </section>
    </div>
  );
}
