/* Autocomplete personalizado — dropdown na cor do header em todas as buscas.
 *
 * O navegador não permite estilizar o dropdown nativo do <datalist> (no
 * Chrome/Edge ele é desenhado pelo sistema). Este script usa o datalist
 * #sugestoes-itens já presente nas páginas como FONTE DE DADOS e desenha
 * o dropdown com o estilo do header (fundo escuro, bordas quadradas).
 */
(function () {
  "use strict";

  var MAX_ITENS = 8;

  function normalizar(texto) {
    return texto
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, ""); // remove acentos ("Capacete" == "capacete")
  }

  function escapeHtml(texto) {
    var div = document.createElement("div");
    div.textContent = texto;
    return div.innerHTML;
  }

  function criarLista() {
    var lista = document.createElement("div");
    lista.className = "autocomplete-lista";
    lista.style.display = "none";
    document.body.appendChild(lista);
    return lista;
  }

  function fechar(lista) {
    lista.style.display = "none";
    lista.dataset.aberta = "0";
  }

  function posicionar(lista, input) {
    var ret = input.getBoundingClientRect();
    lista.style.left = ret.left + "px";
    lista.style.top = ret.bottom + 4 + "px";
    lista.style.width = ret.width + "px";
  }

  function renderizar(lista, input, opcoes) {
    var digitado = normalizar(input.value.trim());
    if (!digitado) {
      fechar(lista);
      return;
    }

    var itens = [];
    opcoes.forEach(function (opcao) {
      var rotulo = opcao.getAttribute("label") || opcao.textContent.trim();
      var jaCompleto = opcao.value.trim().toLowerCase() === input.value.trim().toLowerCase();
      if (!jaCompleto && normalizar(opcao.value).indexOf(digitado) !== -1) {
        itens.push({ valor: opcao.value, rotulo: rotulo });
      }
    });
    if (!itens.length) {
      fechar(lista);
      return;
    }

    lista.innerHTML = "";
    itens.slice(0, MAX_ITENS).forEach(function (item, indice) {
      var linha = document.createElement("div");
      linha.className = "autocomplete-item";
      linha.dataset.indice = indice;
      linha.innerHTML =
        '<span class="autocomplete-nome">' + escapeHtml(item.valor) + "</span>" +
        '<span class="autocomplete-info">' + escapeHtml(item.rotulo) + "</span>";
      lista.appendChild(linha);
    });

    posicionar(lista, input);
    lista.style.display = "block";
    lista.dataset.aberta = "1";
  }

  function destacar(lista, item) {
    var atual = lista.querySelector(".autocomplete-item.ativo");
    if (atual) {
      atual.classList.remove("ativo");
    }
    if (item) {
      item.classList.add("ativo");
      item.scrollIntoView({ block: "nearest" });
    }
  }

  function preparar(input, datalist) {
    var lista = criarLista();
    var opcoes = Array.prototype.slice.call(datalist.querySelectorAll("option"));
    // remove o atributo para o navegador não abrir o dropdown nativo junto
    input.removeAttribute("list");
    // suprime o autocomplete/histórico do navegador e a correção ortográfica
    input.setAttribute("autocomplete", "off");
    input.setAttribute("spellcheck", "false");
    input.setAttribute("autocapitalize", "off");

    input.addEventListener("input", function () {
      renderizar(lista, input, opcoes);
    });

    input.addEventListener("keydown", function (evento) {
      if (lista.dataset.aberta !== "1") {
        return;
      }
      var itens = lista.querySelectorAll(".autocomplete-item");
      var ativo = lista.querySelector(".autocomplete-item.ativo");

      if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
        evento.preventDefault();
        var indice = ativo ? parseInt(ativo.dataset.indice, 10) : -1;
        indice += evento.key === "ArrowDown" ? 1 : -1;
        indice = (indice + itens.length) % itens.length;
        destacar(lista, itens[indice]);
      } else if (evento.key === "Enter") {
        if (ativo) {
          // preenche o campo; o próximo Enter submete normalmente
          evento.preventDefault();
          input.value = ativo.querySelector(".autocomplete-nome").textContent;
          fechar(lista);
        }
      } else if (evento.key === "Escape") {
        fechar(lista);
      }
    });

    lista.addEventListener("mousedown", function (evento) {
      var linha = evento.target.closest(".autocomplete-item");
      if (linha) {
        evento.preventDefault(); // evita o blur do input antes do clique
        input.value = linha.querySelector(".autocomplete-nome").textContent;
        fechar(lista);
        input.focus();
      }
    });

    input.addEventListener("blur", function () {
      setTimeout(function () {
        fechar(lista); // o delay deixa o clique na lista registrar antes
      }, 150);
    });

    window.addEventListener("scroll", function () { fechar(lista); }, true);
    window.addEventListener("resize", function () { fechar(lista); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    // vale para qualquer input com list="<id-do-datalist>"
    document.querySelectorAll("input[list]").forEach(function (input) {
      var datalist = document.getElementById(input.getAttribute("list"));
      if (datalist) {
        preparar(input, datalist);
      }
    });
  });
})();
