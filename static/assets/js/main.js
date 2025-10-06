document.addEventListener("DOMContentLoaded", function () {

        // Config
    // Set FAKE to true to use mocked responses without backend
    const FAKE = false;
    const LATENCY_MS = 300; // Simulated latency for demo
    const API_URL = "/chat";

    const conversacion = document.getElementById("conversacion");
    const entrada = document.getElementById("entrada");
    const enviarBtn = document.getElementById("enviar");
    const badge = document.getElementById("mode-badge");
    badge.textContent = FAKE ? "Demo" : "Live";
    badge.classList.toggle("off", !FAKE);

    function scrollAbajo() {
      conversacion.scrollTop = conversacion.scrollHeight;
    }

    // Simple mock engine for common queries
    // Comments are in English and without symbols
    function mockAnswer(q) {
      const text = q.toLowerCase();

      if (text.includes("cumple") || text.includes("birthday")) {
        return "El día de tu cumpleaños lo tienes libre por defecto. Pídelo con antelación en la página de Vacaciones.";
      }

      if (text.includes("vacacion") && (text.includes("cuánt") || text.includes("numero") || text.includes("días"))) {
        return "El número de días de vacaciones depende de la política vigente. Revisa la página de Vacaciones para el detalle.";
      }

      if (text.includes("vacacion") && (text.includes("página") || text.includes("información"))) {
        return "En la página de Vacaciones encontrarás cómo solicitarlas, plazos mínimos, excepciones y procesos relacionados con producción.";
      }

      if (text.includes("onboard") || text.includes("bienvenida")) {
        return "La guía de onboarding incluye checklist de acceso, herramientas, procesos y primeros pasos en Garaje de Ideas.";
      }

      if (text.includes("intranet") || text.includes("soporte")) {
        return "Para accesos a la intranet o soporte, contacta al equipo correspondiente y revisa los procedimientos internos.";
      }

      return "No tengo esa información en el contexto de esta demo. Intenta ser más específico o consulta la página relacionada en G.book.";
    }

    function enviarPregunta() {
      const pregunta = entrada.value.trim();
      if (!pregunta) return;

      conversacion.querySelectorAll('.appear').forEach(el => el.classList.remove('appear'));

      conversacion.innerHTML += `<span class="user appear"> ${pregunta}</span>`;
      entrada.value = "";
      scrollAbajo();

      if (FAKE) {
        // Simulated response without network
        setTimeout(() => {
          conversacion.querySelectorAll('.appear').forEach(el => el.classList.remove('appear'));
          const data = { respuesta: mockAnswer(pregunta) };
          conversacion.innerHTML += `<span class="bot appear">${data.respuesta}</span>`;
          scrollAbajo();
        }, LATENCY_MS);
        return;
      }

      // Real backend call when FAKE is false
      fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: pregunta })
      })
      .then(res => {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(data => {
        conversacion.innerHTML += `<span class="bot">${data.respuesta}</span>`;
        scrollAbajo();
      })
      .catch(err => {
        conversacion.innerHTML += `<span class="bot">Error: ${err.message}</span> `;
        scrollAbajo();
      });
    }

    enviarBtn.addEventListener("click", enviarPregunta);
    entrada.addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        enviarPregunta();
      }
    });
});