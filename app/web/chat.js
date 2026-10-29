'use strict';
const $ = id => document.getElementById(id);
let busy = false;
const welcome = $('welcome').cloneNode(true);
function clearMessages() { $('messages').replaceChildren(welcome.cloneNode(true)); bindSuggestions(); }
function bindSuggestions() { document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => { $('message').value = button.dataset.prompt; $('message-form').requestSubmit(); })); }
async function api(path, body) {
  const response = await fetch(path, {method:body === undefined ? 'GET':'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.detail || (response.status === 401 ? 'Sua sessão expirou. Entre novamente.' : 'Não foi possível concluir. Tente novamente.')); error.status=response.status; throw error; }
  return data;
}
function authenticated(data) {
  $('login-panel').hidden = data.authenticated; $('chat-panel').hidden = !data.authenticated;
  $('reset').hidden = !data.authenticated; $('logout').hidden = !data.authenticated;
  if (data.authenticated) { $('mode-note').textContent = data.reviewed_catalog ? 'Teste interno com fatos verificados: autonomia do C10 BEV. Fotos reais ainda aguardam aprovação.' : 'Catálogo de atendimento em revisão. Informações e fotos pendentes não serão exibidas.'; $('message').focus(); }
}
function append(text, who, pending=false) {
  $('welcome')?.remove();
  const article=document.createElement('article'); article.className='message '+who+(pending ? ' pending':'');
  const label=document.createElement('p'); label.className='who'; label.textContent=who === 'user' ? 'Você':'LEAP';
  const bubble=document.createElement('div'); bubble.className='bubble'; bubble.textContent=text;
  article.append(label,bubble); $('messages').append(article); article.scrollIntoView({block:'end'}); return article;
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault(); $('login-error').textContent=''; $('login-button').disabled=true;
  try { const data=await api('/web/login',{password:$('password').value, reviewed_catalog:$('catalog-mode').value==='reviewed'}); $('password').value=''; clearMessages(); authenticated(data); }
  catch(error) { $('login-error').textContent=error.message; }
  finally { $('login-button').disabled=false; }
});
$('message-form').addEventListener('submit', async event => {
  event.preventDefault(); const text=$('message').value.trim(); if (!text || busy) return;
  busy=true; $('send').disabled=true; $('reset').disabled=true; $('logout').disabled=true; $('chat-error').textContent=''; $('message').value='';
  append(text,'user'); const thinking=append('Consultando informações…','assistant',true);
  try { const result=await api('/v1/web/messages',{text}); thinking.remove(); const article=append(result.text,'assistant');
    if (result.source_ids?.length) { const ref=document.createElement('div'); ref.className='reference'; ref.textContent='Fonte verificada · '+result.source_ids.join(', '); article.append(ref); }
    if (result.media_ids?.length) { const ref=document.createElement('div'); ref.className='reference'; ref.textContent='Imagens localizadas: '+result.media_ids.join(', '); article.append(ref); }
  } catch(error) { thinking.remove(); $('chat-error').textContent=error.message; if(error.status === 401) authenticated({authenticated:false}); }
  finally {busy=false; $('send').disabled=false; $('reset').disabled=false; $('logout').disabled=false; $('message').focus();}
});
$('message').addEventListener('keydown', event => {if(event.key==='Enter' && !event.shiftKey && !event.isComposing) {event.preventDefault(); $('message-form').requestSubmit();}});
$('reset').addEventListener('click',async()=>{try {await api('/web/reset',{}); clearMessages(); $('message').focus();}catch(error){$('chat-error').textContent=error.message;}});
$('logout').addEventListener('click',async()=>{try {await api('/web/logout',{}); clearMessages(); authenticated({authenticated:false});}catch(error){$('chat-error').textContent=error.message;}});
bindSuggestions();
api('/web/session').then(authenticated).catch(()=>authenticated({authenticated:false}));
