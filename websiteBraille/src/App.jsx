import { useState, useRef, useEffect } from 'react';
import './index.css';

function App() {
  const [outputImage, setOutputImage] = useState(null);
  const [dotViewImage, setDotViewImage] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const [pyodideReady, setPyodideReady] = useState(false);
  const [initMessage, setInitMessage] = useState("Browser-KI-Engine wird initialisiert...");
  const pyodideInstance = useRef(null);

  useEffect(() => {
    async function initPyodide() {
      if (pyodideInstance.current) return;
      try {
        setInitMessage("Computer-Vision-Module werden heruntergeladen (dies geschieht nur einmal)...");
        // Load Pyodide from CDN linked in index.html
        if (!window.loadPyodide) {
           throw new Error("Pyodide script failed to load in index.html.");
        }

        const pyodide = await window.loadPyodide({
          indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
        });
        
        setInitMessage("Computer-Vision-Arrays werden verknüpft...");
        await pyodide.loadPackage(["opencv-python", "numpy", "scipy"]);
        
        setInitMessage("Python-Kern wird kompiliert...");
        // Fetch the python logic we stored in public folder
        const response = await fetch('/py_processor.py');
        const pyCode = await response.text();
        
        await pyodide.runPythonAsync(pyCode);
        
        pyodideInstance.current = pyodide;
        setPyodideReady(true);
      } catch (e) {
        console.error(e);
        setError("Fehler beim Initialisieren der lokalen Python-Engine. " + e.message);
      }
    }
    
    initPyodide();
  }, []);


  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (!pyodideReady || !pyodideInstance.current) {
        setError("Bitte warten Sie, bis die KI-Engine initialisiert ist.");
        return;
    }

    setIsLoading(true);
    setError(null);
    setOutputImage(null);
    setDotViewImage(null);

    try {
      const arrayBuffer = await file.arrayBuffer();
      const uint8Array = new Uint8Array(arrayBuffer);
      
      const pyodide = pyodideInstance.current;
      
      // Inject JS array directly into Pyodide global namespace
      pyodide.globals.set("image_bytes", uint8Array);
      
      // Call the python function
      const result = await pyodide.runPythonAsync(`
process_braille_fast_bytes(image_bytes)
      `);
      
      // Pyodide returns a JsProxy tuple, we convert to a native JS Array
      const jsArray = result.toJs();
      const out_b64 = jsArray[0];
      const dot_b64 = jsArray[1];
      result.destroy(); // memory cleanup of proxy

      if (out_b64 && dot_b64) {
        setOutputImage(`data:image/jpeg;base64,${out_b64}`);
        setDotViewImage(`data:image/jpeg;base64,${dot_b64}`);
      } else {
        throw new Error("Keine Braille-Punkte erfolgreich identifiziert (mindestens 2 Punkte erforderlich).");
      }
    } catch (err) {
      console.error(err);
      setError(err.message || "Beim Verarbeiten des Bildes ist ein Fehler aufgetreten.");
    } finally {
      setIsLoading(false);
    }
    
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>Kamera-Braille</h1>
        <p>Erweiterte optische Erkennung für strukturelle Braille-Muster</p>
      </header>

      <main>
        <section className="upload-section">
          <div className="upload-card">
            <svg 
              width="64" 
              height="64" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="#818cf8" 
              strokeWidth="1.5" 
              strokeLinecap="round" 
              strokeLinejoin="round"
              style={{ marginBottom: '1rem', strokeLinecap: 'round', strokeLinejoin: 'round' }}
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <h2>Braille hochladen oder aufnehmen</h2>
            <p style={{ color: '#94a3b8', marginBottom: '1rem' }}>
              Wählen Sie ein Foto von Ihrem Gerät aus oder machen Sie ein neues, um mit der Verarbeitung zu beginnen.
            </p>

            {!pyodideReady && !error && (
              <div style={{ marginBottom: '1rem', padding: '1rem', background: 'rgba(129, 140, 248, 0.1)', borderRadius: '0.5rem', color: '#818cf8' }}>
                <div className="loader" style={{width: '24px', height: '24px', borderWidth: '3px', marginBottom: '0.5rem'}}></div>
                {initMessage}
              </div>
            )}
            
            <div className="file-input-wrapper">
              <button className="btn-upload" style={{ opacity: pyodideReady && !isLoading ? 1 : 0.5 }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>
                Bild auswählen
              </button>
              <input 
                type="file" 
                accept="image/*" 
                capture="environment" 
                onChange={handleFileUpload} 
                ref={fileInputRef}
                disabled={!pyodideReady || isLoading}
              />
            </div>
            
            {isLoading && (
              <div style={{ marginTop: '2rem' }}>
                <div className="loader"></div>
                <div className="status-message">Struktur und physische Tiefe werden nativ analysiert...</div>
              </div>
            )}
            
            {error && (
              <div className="error-message">
                {error}
              </div>
            )}
          </div>
        </section>

        {(outputImage || dotViewImage) && (
          <section className="results-section">
            {outputImage && (
              <div className="image-card">
                <h3>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#818cf8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                  Zwei-Phasen-Schnellfilter
                </h3>
                <div className="image-wrapper">
                  <img src={outputImage} alt="Analyseergebnis" />
                </div>
              </div>
            )}
            
            {dotViewImage && (
              <div className="image-card">
                <h3>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#c084fc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="3"></circle></svg>
                  Nur Braille-Punkte
                </h3>
                <div className="image-wrapper">
                  <img src={dotViewImage} alt="Extrahierte Braille-Punkte" />
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
