import { useState } from "react";
import Reveal from "../components/Reveal";

const GITHUB_URL = "https://github.com/OppositeMusical";
const LINKEDIN_URL = "https://www.linkedin.com/in/christepher-irving-028437294/";
const EMAIL = "ChristepherIrving11@gmail.com";

/**
 * Drop a headshot at frontend/public/christepher-irving.jpg to use it.
 * Until then the initials mark stands in - see the onError below, which
 * means a missing file degrades to the mark instead of a broken image.
 */
const PHOTO_SRC = "/christepher-irving.jpg";

const EXPERIENCE = [
  {
    role: "Freelance Software Engineer",
    org: "Ferguson Solutions",
    when: "Jun 2026 – Present",
    where: "Wilmington, DE",
    points: [
      "Architected and deployed a secure enterprise order and inventory management tool for Desserts by Dana Bakery using Python, Streamlit and SQLite3.",
      "Implemented role-based access control with cryptography, restricting permissions across executive, managerial and staff roles.",
      "Automated printable document workflows with ReportLab, generating order receipts and inter-branch requisition forms.",
    ],
  },
  {
    role: "IT Repair Technician Contractor",
    org: "Inspiroz",
    when: "Jun 2026 – Aug 2026",
    where: "Chadds Ford, PA",
    points: [
      "Diagnosed, repaired and reconfigured hardware across 1,000+ HP G8, G9 and G10 Chromebooks.",
      "Reconciled database mismatches with management to correct mislabeled inventory records before school redistribution.",
    ],
  },
  {
    role: "AI Research Intern",
    org: "NASA / Delaware Space Grant Consortium",
    when: "Jun 2025 – Jun 2026",
    where: "Newark, DE",
    points: [
      "Engineered a retrieval-augmented generation model in Python powering an AI-enhanced learning management system.",
      "Built a drag-and-drop workflow editor with ReactFlow and Streamlit, letting educators assemble custom RAG agents in minutes.",
      "Partnered with local schools for usability feedback and presented findings at the University of Delaware Symposium.",
    ],
  },
  {
    role: "Ag/Bio AI Research Intern",
    org: "Delaware State University",
    when: "May 2025 – Aug 2025",
    where: "Dover, DE",
    points: [
      "Built a mobile-friendly app using Python, a RAG pipeline and the PlantID API to assess plant health from user photos.",
      "Added a conversational chatbot for follow-up botanical questions; presented at DSU's Summer Research Symposium.",
    ],
  },
  {
    role: "Snap Frames Research Extern",
    org: "Extern / Snap Inc.",
    when: "Sep 2024 – Nov 2024",
    where: "Remote",
    points: [
      "Researched user interaction patterns with AR Snap Frames in Snapchat's Lens Studio.",
      "Presented findings and interactive prototypes to stakeholders, researchers and company leadership.",
    ],
  },
  {
    role: "Customer Service Associate",
    org: "Wawa",
    when: "Nov 2022 – Present",
    where: "New Castle, DE",
    points: [
      "Ran multi-department operations across food, beverage and register while coordinating employee shift breaks.",
    ],
  },
];

const SKILLS = [
  { group: "Languages", items: ["Python", "JavaScript", "TypeScript", "Java", "C++", "SQL"] },
  {
    group: "Frameworks & tools",
    items: ["React", "Flask", "FastAPI", "Streamlit", "Electron", "ReactFlow", "ReportLab", "Ollama", "REST APIs"],
  },
  { group: "Developer tools", items: ["Git", "GitHub", "VS Code", "Antigravity", "Claude Code"] },
];

const LEADERSHIP = [
  {
    org: "National Society of Black Engineers (NSBE)",
    role: "Executive Board Member",
    when: "Aug 2025 – May 2026",
    detail: "Coordinated academic and career development workshops for collegiate engineering students.",
  },
  {
    org: "Computer Science Student Association",
    role: "Executive Board Member",
    when: "Aug 2022 – Jun 2025",
    detail: "Organised technical seminars, coding challenges and peer mentorship for CS undergraduates.",
  },
];

export default function About() {
  // Falls back to the initials mark rather than a broken-image icon.
  const [photoFailed, setPhotoFailed] = useState(false);

  return (
    <section className="section section--first">
      <div className="container">
        <Reveal from="scale">
          <div className="dev-profile">
            {photoFailed ? (
              <div className="dev-profile__mark" aria-hidden="true">
                CI
              </div>
            ) : (
              <img
                className="dev-profile__photo"
                src={PHOTO_SRC}
                alt="Christepher Irving"
                onError={() => setPhotoFailed(true)}
              />
            )}
            <div className="dev-profile__text">
              <span className="dev-profile__status">Open to opportunities</span>
              <h1>Christepher Irving</h1>
              <p className="dev-profile__role">
                Software Engineer &middot; B.S. Computer Science, Delaware State University
              </p>
              <p className="dev-profile__where">Wilmington, Delaware</p>
              <div className="dev-profile__links">
                <a href={GITHUB_URL} target="_blank" rel="noreferrer">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 .5a12 12 0 0 0-3.79 23.4c.6.1.82-.26.82-.58v-2c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.1-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.8 5.62-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.69.83.57A12 12 0 0 0 12 .5z" />
                  </svg>
                  GitHub
                </a>
                <a href={LINKEDIN_URL} target="_blank" rel="noreferrer">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.42v1.56h.05a3.75 3.75 0 0 1 3.37-1.85c3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.07 2.07 0 1 1 0-4.14 2.07 2.07 0 0 1 0 4.14zm1.78 13.02H3.55V9h3.57v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.72V1.72C24 .77 23.2 0 22.22 0z" />
                  </svg>
                  LinkedIn
                </a>
                <a href={`mailto:${EMAIL}`}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <rect x="2" y="4" width="20" height="16" rx="2" />
                    <path d="m2 7 10 6 10-6" />
                  </svg>
                  Email
                </a>
              </div>
            </div>
          </div>
        </Reveal>

        <Reveal delay={90}>
          <div className="dev-intro">
            <p>
              I studied computer science at Delaware State University, and I build things end to end.
              Most of my work has been on <strong>retrieval-augmented AI systems</strong> — a RAG
              model behind an AI-enhanced learning platform at{" "}
              <strong>NASA's Delaware Space Grant Consortium</strong>, a plant-health app pairing a RAG
              pipeline with the PlantID API, and the prediction engine behind this site.
            </p>
            <p>
              MMA Assist is where most of that comes together: a Python and Flask backend, a ChromaDB
              retrieval layer over a scraped database of <strong>6,746 UFC fighters</strong>, five
              interchangeable AI providers from local Ollama models to the Claude and OpenAI APIs, and
              an Electron desktop app that code-signs and updates itself. The parts I find most
              interesting are usually the unglamorous ones — making a scraper resume cleanly after a
              55-hour run, or getting an app to replace its own binary while a Python server still has
              the file open.
            </p>
          </div>
        </Reveal>

        <Reveal className="section__heading">
          <h2>Experience</h2>
        </Reveal>
        <div className="timeline">
          {EXPERIENCE.map((job, i) => (
            <Reveal key={`${job.org}-${job.role}`} from="left" delay={Math.min(i * 70, 280)}>
              <article className="timeline__item">
                <header className="timeline__head">
                  <div>
                    <h3>{job.role}</h3>
                    <p className="timeline__org">{job.org}</p>
                  </div>
                  <div className="timeline__meta">
                    <span>{job.when}</span>
                    <span>{job.where}</span>
                  </div>
                </header>
                <ul>
                  {job.points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
              </article>
            </Reveal>
          ))}
        </div>

        <Reveal className="section__heading">
          <h2>Skills</h2>
        </Reveal>
        <div className="skills">
          {SKILLS.map((row, i) => (
            <Reveal key={row.group} delay={i * 80}>
              <div className="skills__row">
                <h3>{row.group}</h3>
                <ul>
                  {row.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal className="section__heading">
          <h2>Leadership</h2>
        </Reveal>
        <div className="timeline">
          {LEADERSHIP.map((entry, i) => (
            <Reveal key={entry.org} from="left" delay={i * 80}>
              <article className="timeline__item">
                <header className="timeline__head">
                  <div>
                    <h3>{entry.role}</h3>
                    <p className="timeline__org">{entry.org}</p>
                  </div>
                  <div className="timeline__meta">
                    <span>{entry.when}</span>
                  </div>
                </header>
                <ul>
                  <li>{entry.detail}</li>
                </ul>
              </article>
            </Reveal>
          ))}
        </div>

        <Reveal from="scale" delay={60}>
          <div className="dev-cta">
            <a className="btn btn--primary" href={`mailto:${EMAIL}`}>
              Get in touch
            </a>
            <a className="btn btn--secondary" href={GITHUB_URL} target="_blank" rel="noreferrer">
              Browse the code on GitHub
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
